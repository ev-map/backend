"""
Parser for French IRVE (Infrastructures de Recharge pour Véhicules Électriques)
static charging station data in CSV format.

Data schema: https://schema.data.gouv.fr/etalab/schema-irve-statique/2.3.1/documentation.html

The CSV has one row per point de charge (chargepoint). Rows sharing the same
``id_station_itinerance`` belong to the same charging site.
"""

import csv
import logging
import re
from collections import defaultdict
from typing import Dict, Iterable, List

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError

from evmap_backend.chargers.fields import normalize_evseid, validate_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources.sync import ChargepointItem, ChargingSiteItem
from evmap_backend.helpers.database import none_to_blank

logger = logging.getLogger(__name__)

# IRVE prise_type_* boolean columns -> ConnectorType mapping
PLUG_TYPE_MAP: Dict[str, Connector.ConnectorTypes] = {
    "prise_type_ef": Connector.ConnectorTypes.DOMESTIC_E,
    "prise_type_2": Connector.ConnectorTypes.TYPE_2,
    "prise_type_combo_ccs": Connector.ConnectorTypes.CCS_TYPE_2,
    "prise_type_chademo": Connector.ConnectorTypes.CHADEMO,
    "prise_type_autre": Connector.ConnectorTypes.OTHER,
}

# Connector types that sockets by default (no attached cable)
SOCKET_CONNECTOR_TYPES = {
    Connector.ConnectorTypes.DOMESTIC_E,
    Connector.ConnectorTypes.TYPE_2,
}


def _parse_bool(value: str) -> bool:
    """Parse a boolean from IRVE CSV (TRUE/FALSE or true/false)."""
    return value.strip().upper() == "TRUE"


def _parse_float(value: str) -> float:
    """Parse a float, returning 0.0 on failure."""
    try:
        return float(value.strip().replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _parse_coordinates(row: dict) -> Point | None:
    """Parse consolidated_longitude / consolidated_latitude into a Point."""
    try:
        lng = float(row.get("consolidated_longitude", "").strip().replace(",", "."))
        lat = float(row.get("consolidated_latitude", "").strip().replace(",", "."))
    except (ValueError, TypeError, AttributeError):
        return None

    if lat == 0 and lng == 0:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None

    return Point(lng, lat)


def _parse_connectors(row: dict) -> List[Connector]:
    """Build connectors from the prise_type_* boolean columns in a single row."""
    power_kw = _parse_float(row.get("puissance_nominale", "0"))
    max_power = power_kw * 1000  # convert kW to W

    cable_attached = _parse_bool(row.get("cable_t2_attache", "FALSE"))

    connectors = []
    for column, connector_type in PLUG_TYPE_MAP.items():
        if _parse_bool(row.get(column, "FALSE")):
            if connector_type in SOCKET_CONNECTOR_TYPES and not cable_attached:
                connector_format = Connector.ConnectorFormats.SOCKET
            else:
                connector_format = Connector.ConnectorFormats.CABLE

            connectors.append(
                Connector(
                    connector_type=connector_type,
                    connector_format=connector_format,
                    max_power=max_power,
                )
            )

    return connectors


_ADDRESS_PATTERN = re.compile(r"^(.*?)\s+(\d{5})\s+(.+)$")


def _parse_address(address: str) -> tuple[str, str]:
    """Extract (zipcode, city) from a French address string.

    The ``adresse_station`` field typically looks like
    ``"Rue Lamartine 31110 Bagnères-de-Luchon"``.  We try to extract the
    5-digit postal code and the city name that follows it.

    Returns (zipcode, city) — both may be empty if parsing fails.
    """
    m = _ADDRESS_PATTERN.match(address)
    if m:
        return m.group(2), m.group(3)
    return "", ""


def parse_irve_csv(
    lines: Iterable[str],
    data_source: str,
    license_attribution: str,
    license_attribution_link: str,
) -> Iterable[ChargingSiteItem]:
    """
    Parse IRVE CSV data and yield ChargingSiteItem objects.

    Rows are grouped by ``id_station_itinerance`` to form charging sites,
    each containing one or more chargepoints.

    ``lines`` should be an iterable of decoded text lines (e.g. from
    ``response.iter_lines(decode_unicode=True)``).
    """
    reader = csv.DictReader(lines, delimiter=",")

    # Group rows by station ID
    stations: Dict[str, List[dict]] = defaultdict(list)
    for row in reader:
        station_id = row.get("id_station_itinerance", "").strip()
        if not station_id:
            continue
        stations[station_id].append(row)

    for station_id, rows in stations.items():
        first_row = rows[0]

        location = _parse_coordinates(first_row)
        if location is None:
            logger.warning(
                f"Skipping station {station_id}: invalid coordinates "
                f"({first_row.get('consolidated_longitude')}, {first_row.get('consolidated_latitude')})"
            )
            continue

        # Determine network from EVSE ID prefix
        network = None
        first_evseid = normalize_evseid(first_row["id_pdc_itinerance"])
        try:
            validate_evseid(first_evseid)
            evse_operator_id = first_evseid[:5]
            if evse_operator_id:
                operator_name = none_to_blank(first_row.get("nom_operateur"))
                network, _ = Network.get_or_create(
                    evse_operator_id=evse_operator_id,
                    defaults=dict(name=operator_name),
                )
        except ValidationError:
            # Station IDs may not always be valid EVSEIDs
            pass

        # Build site-level EVSEID if valid
        site_evseid = ""
        try:
            validate_evseid(station_id)
            site_evseid = station_id
        except ValidationError:
            pass

        # The adresse_station field often contains "Street PostalCode City"
        # Try to extract zipcode and city from it
        address_raw = none_to_blank(first_row.get("adresse_station"))
        zipcode, city = _parse_address(address_raw)

        site = ChargingSite(
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=license_attribution_link,
            id_from_source=station_id,
            name=none_to_blank(first_row.get("nom_station")),
            location=location,
            site_evseid=site_evseid,
            network=network,
            operator=none_to_blank(first_row.get("nom_operateur")),
            street=address_raw,
            zipcode=zipcode,
            city=city,
            country="FR",
            opening_hours=none_to_blank(first_row.get("horaires")),
        )

        chargepoints = []
        for row in rows:
            pdc_id = row.get("id_pdc_itinerance", "").strip()
            if not pdc_id:
                continue

            evseid_normalized = normalize_evseid(pdc_id)
            try:
                validate_evseid(evseid_normalized)
            except ValidationError:
                evseid_normalized = ""

            chargepoint = Chargepoint(
                id_from_source=pdc_id,
                evseid=evseid_normalized,
            )

            connectors = _parse_connectors(row)
            chargepoints.append(ChargepointItem(chargepoint, connectors))

        if not chargepoints:
            logger.warning(f"Skipping station {station_id}: no valid chargepoints")
            continue

        yield ChargingSiteItem(site, chargepoints)
