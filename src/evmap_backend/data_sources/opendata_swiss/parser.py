"""
Parser for Opendata Swiss OICP (Hubject) format data from ich-tanke-strom.ch / BFE.

Data format documentation:
- Static data: EVSEData -> [{OperatorID, OperatorName, EVSEDataRecord: [...]}]
- Status data: EVSEStatuses -> [{OperatorID, OperatorName, EVSEStatusRecord: [...]}]

Each EVSEDataRecord represents a single EVSE (chargepoint).
EVSEs are grouped into charging sites by (OperatorID, location cluster).  Nearby
coordinates (within ~50 m) are merged using leader clustering because the
ChargingStationId field is unreliable (some operators copy the EvseID, others use
one ID per physical charging pole) and some operators report slightly different GPS
positions for chargers at the same location.
"""

import logging
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.utils import timezone
from opening_hours import OpeningHours

from evmap_backend.chargers.fields import normalize_evseid, validate_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources.sync import (
    ChargepointItem,
    ChargingSiteItem,
    RealtimeStatusItem,
)
from evmap_backend.helpers.database import none_to_blank
from evmap_backend.realtime.models import RealtimeStatus

logger = logging.getLogger(__name__)

# ISO 3166-1 alpha-3 to alpha-2 country code mapping (for codes found in data)
COUNTRY_CODE_MAP = {
    "CHE": "CH",
    "41": "CH",  # some records use the phone country code
}

# OICP plug type to our connector type mapping
PLUG_TYPE_MAP: Dict[str, Connector.ConnectorTypes] = {
    "Type 2 Outlet": Connector.ConnectorTypes.TYPE_2,
    "Type 2 Connector (Cable Attached)": Connector.ConnectorTypes.TYPE_2,
    "Type 1 Connector (Cable Attached)": Connector.ConnectorTypes.TYPE_1,
    "CCS Combo 2 Plug (Cable Attached)": Connector.ConnectorTypes.CCS_TYPE_2,
    "CCS Combo 1 Plug (Cable Attached)": Connector.ConnectorTypes.CCS_TYPE_1,
    "CHAdeMO": Connector.ConnectorTypes.CHADEMO,
    "Type F Schuko": Connector.ConnectorTypes.SCHUKO,
    "Type J Swiss Standard": Connector.ConnectorTypes.DOMESTIC_J,
    "Tesla Connector": Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
}

# OICP plug types that indicate a socket (vs. attached cable)
SOCKET_PLUG_TYPES = {
    "Type 2 Outlet",
    "Type F Schuko",
    "Type J Swiss Standard",
}

# OICP status to OCPI-style status mapping
STATUS_MAP: Dict[str, RealtimeStatus.Status] = {
    "Available": RealtimeStatus.Status.AVAILABLE,
    "Occupied": RealtimeStatus.Status.CHARGING,
    "OutOfService": RealtimeStatus.Status.OUTOFORDER,
    "Reserved": RealtimeStatus.Status.RESERVED,
    "Unknown": RealtimeStatus.Status.UNKNOWN,
}

# Day name mapping for opening hours conversion to OSM format
DAY_ABBREVIATIONS = {
    "Monday": "Mo",
    "Tuesday": "Tu",
    "Wednesday": "We",
    "Thursday": "Th",
    "Friday": "Fr",
    "Saturday": "Sa",
    "Sunday": "Su",
}


def _parse_coordinates(geo_coordinates: dict) -> Optional[Point]:
    """Parse GeoCoordinates in Google format ('lat lng') to a Point."""
    google = geo_coordinates.get("Google", "")
    parts = google.split()
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lng = float(parts[1])
        if lat == 0 and lng == 0:
            return None
        return Point(lng, lat)
    except (ValueError, TypeError):
        return None


# Maximum distance (in degrees) for two EVSEs to be considered part of the same site.
# At ~47°N (Switzerland): 0.0005° ≈ 55 m lat, ~37 m lng.  Using the same threshold
# for both axes is a simple approximation that works well in practice.
_CLUSTER_THRESHOLD = 0.0005


def _parse_google_coords(google_coords: str) -> Optional[Tuple[float, float]]:
    """Parse a 'lat lng' string into a (lat, lng) tuple, or None."""
    parts = google_coords.split()
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except (ValueError, TypeError):
        return None


class _SiteClusterer:
    """Assign EVSE records to site clusters using leader clustering.

    For each operator the first record at a new location becomes a cluster leader.
    Subsequent records within ``_CLUSTER_THRESHOLD`` degrees of an existing leader
    join that cluster.

    The cluster key is the formatted coordinate of the leader (first record seen).
    """

    def __init__(self):
        # (operator_id, operator_name) -> list of (leader_lat, leader_lng, key_str)
        self._leaders: Dict[Tuple[str, str], List[Tuple[float, float, str]]] = (
            defaultdict(list)
        )

    def get_cluster_key(
        self, operator_id: str, operator_name: str, google_coords: str
    ) -> str:
        """Return a stable cluster key for the given record coordinates."""
        parsed = _parse_google_coords(google_coords)
        if parsed is None:
            return google_coords  # unparseable – use raw string

        lat, lng = parsed
        op_key = (operator_id, operator_name)
        for leader_lat, leader_lng, key_str in self._leaders[op_key]:
            if (
                abs(lat - leader_lat) < _CLUSTER_THRESHOLD
                and abs(lng - leader_lng) < _CLUSTER_THRESHOLD
            ):
                return key_str

        # No nearby leader found – start a new cluster
        key_str = f"{lat:.6f} {lng:.6f}"
        self._leaders[op_key].append((lat, lng, key_str))
        return key_str


def _get_station_name(record: dict) -> str:
    """Get the station name from ChargingStationNames, preferring English."""
    names = record.get("ChargingStationNames") or []
    if not names:
        return ""

    if isinstance(names, dict):
        names = [names]  # Handle case where it's a single object instead of a list
    elif not isinstance(names, list):
        return ""

    # Prefer English, then German, then first available
    for preferred_lang in ("en", "de", "fr", "it"):
        for name_entry in names:
            if (
                isinstance(name_entry, dict)
                and name_entry.get("lang") == preferred_lang
            ):
                return name_entry.get("value", "")

    first = names[0]
    if isinstance(first, dict):
        return first.get("value", "")
    return ""


def _convert_opening_hours(record: dict) -> str:
    """Convert OICP opening times to OSM opening_hours format.

    Builds a raw opening_hours string from the OICP data and then uses the
    ``opening_hours`` library to normalize it (merging consecutive days into
    ranges, etc.).
    """
    if record.get("IsOpen24Hours"):
        return "24/7"

    opening_times = record.get("OpeningTimes")
    if not opening_times:
        return ""

    # Build individual "Day HH:MM-HH:MM" rules and let the library normalize.
    # Structure: [{on: "Monday", Period: [{begin: "05:20", end: "20:50"}]}, ...]
    parts = []
    for entry in opening_times:
        day_name = entry.get("on", "")
        day_abbr = DAY_ABBREVIATIONS.get(day_name)
        if not day_abbr:
            continue

        periods = entry.get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]  # Handle case where it's a single object
        for period in periods:
            begin = period.get("begin", "")
            end = period.get("end", "")
            if begin and end:
                parts.append(f"{day_abbr} {begin}-{end}")

    if not parts:
        return ""

    raw = "; ".join(parts)
    return str(OpeningHours(raw).normalize())


def _parse_connectors(record: dict) -> List[Connector]:
    """Parse connectors from an EVSE data record.

    Each EVSE record has a list of Plugs and a list of ChargingFacilities.
    We match them by index where possible; if counts differ, we use the
    charging facility power for all connectors.
    """
    plugs = record.get("Plugs", [])
    facilities = record.get("ChargingFacilities", [])

    connectors = []
    for i, plug in enumerate(plugs):
        connector_type = PLUG_TYPE_MAP.get(plug)
        if connector_type is None:
            logger.warning(
                f"Unknown plug type: {plug} (EvseID: {record.get('EvseID')})"
            )
            connector_type = Connector.ConnectorTypes.OTHER

        connector_format = (
            Connector.ConnectorFormats.SOCKET
            if plug in SOCKET_PLUG_TYPES
            else Connector.ConnectorFormats.CABLE
        )

        # Get power from matching facility or last facility
        max_power = 0.0
        if facilities:
            facility = facilities[min(i, len(facilities) - 1)]
            power_kw = facility.get("power")
            if power_kw is not None:
                try:
                    max_power = float(power_kw) * 1000  # Convert kW to W
                except (ValueError, TypeError):
                    pass

        connectors.append(
            Connector(
                connector_type=connector_type,
                connector_format=connector_format,
                max_power=max_power,
            )
        )

    return connectors


def parse_oicp_data(
    data: dict,
    data_source: str,
    license_attribution: str,
    license_attribution_link: str,
) -> Iterable[ChargingSiteItem]:
    """
    Parse OICP static data and yield (ChargingSite, [(Chargepoint, [Connector])]) tuples.

    EVSEs are grouped into charging sites by (OperatorID, location cluster).
    Nearby coordinates (within ~50 m) are merged into the same site so that
    chargepoints at the same physical location but with slightly different GPS
    positions end up in one site.
    """
    # Group EVSE records by (operator_id, operator_name, cluster_key)
    stations: Dict[Tuple[str, str, str], List[dict]] = defaultdict(list)
    clusterer = _SiteClusterer()

    for evse_data_entry in data.get("EVSEData", []):
        operator_id = evse_data_entry.get("OperatorID", "")
        operator_name = evse_data_entry.get("OperatorName", "")

        for record in evse_data_entry.get("EVSEDataRecord", []):
            raw_coords = record.get("GeoCoordinates", {}).get("Google", "")
            cluster_key = clusterer.get_cluster_key(
                operator_id, operator_name, raw_coords
            )
            key = (operator_id, operator_name, cluster_key)
            stations[key].append(record)

    for (operator_id, operator_name, cluster_key), records in stations.items():
        # Use the first record for site-level information
        first_record = records[0]

        location = _parse_coordinates(first_record.get("GeoCoordinates", {}))
        if location is None:
            logger.warning(f"Skipping station at {cluster_key}: invalid coordinates")
            continue

        address = first_record.get("Address", {})
        country_raw = address.get("Country", "CH")
        country = COUNTRY_CODE_MAP[country_raw]

        first_evseid = normalize_evseid(first_record.get("EvseID", ""))
        network = None
        try:
            validate_evseid(first_evseid)
            evse_operator_id = first_evseid[:5]
            if evse_operator_id:
                network, _ = Network.get_or_create(
                    evse_operator_id=evse_operator_id,
                    defaults=dict(name=none_to_blank(operator_name)),
                )
        except ValidationError:
            logger.warning(f"invalid evseid: {first_evseid}")

        site = ChargingSite(
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=license_attribution_link,
            id_from_source=cluster_key,
            name=_get_station_name(first_record),
            location=location,
            network=network,
            operator=none_to_blank(operator_name),
            street=none_to_blank(address.get("Street")),
            zipcode=none_to_blank(address.get("PostalCode")),
            city=none_to_blank(address.get("City")),
            country=country,
            opening_hours=_convert_opening_hours(first_record),
        )

        chargepoints = []
        for record in records:
            evse_id = record.get("EvseID", "")
            evseid_normalized = normalize_evseid(evse_id)
            try:
                validate_evseid(evseid_normalized)
            except ValidationError:
                evseid_normalized = ""

            chargepoint = Chargepoint(
                id_from_source=evse_id,
                evseid=evseid_normalized,
            )

            connectors = _parse_connectors(record)
            chargepoints.append(ChargepointItem(chargepoint, connectors))

        yield ChargingSiteItem(site, chargepoints)


def parse_oicp_status(
    status_data: dict,
    data_source: str,
    license_attribution: str,
    license_attribution_link: str,
) -> Iterable[RealtimeStatusItem]:
    """
    Parse OICP status data and yield (site_id, RealtimeStatus) tuples.

    Since the status data only contains EvseID and status, and we need the site_id
    for sync_statuses, we need to look up chargepoints from the database.
    We yield (evse_id, RealtimeStatus) where the chargepoint's id_from_source is the EvseID,
    and the site_id needs to be resolved.
    """
    now = timezone.now()

    for status_entry in status_data.get("EVSEStatuses", []):
        for record in status_entry.get("EVSEStatusRecord", []):
            evse_id = record.get("EvseID", "")
            if not evse_id:
                continue

            evse_status = record.get("EVSEStatus", "Unknown")
            status = STATUS_MAP.get(evse_status, RealtimeStatus.Status.UNKNOWN)

            realtime_status = RealtimeStatus(
                status=status,
                timestamp=now,
                data_source=data_source,
                license_attribution=license_attribution,
                license_attribution_link=license_attribution_link,
            )

            yield RealtimeStatusItem(
                chargepoint_id_from_source=evse_id, status=realtime_status
            )
