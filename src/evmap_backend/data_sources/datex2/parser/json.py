import datetime
import json
from typing import Iterable, Optional, Tuple

from tqdm import tqdm

from evmap_backend.data_sources.datex2.parser import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
    Datex2EnergyInfrastructureSiteStatus,
    Datex2MultilingualString,
    Datex2RefillPoint,
    Datex2RefillPointStatus,
    parse_datetime,
)


def parse_multilingual_string(elem) -> Datex2MultilingualString:
    if isinstance(elem, dict) and "values" in elem:
        elem = elem["values"]

    if isinstance(elem, list):
        values = {value["lang"]: value["value"] for value in elem}
    else:
        values = {elem["lang"]: elem["value"] if "value" in elem else ""}

    return Datex2MultilingualString(values=values)


def parse_point_coordinates(elem: dict) -> Tuple[float, float]:
    return (elem["longitude"], elem["latitude"])


def parse_connector(elem) -> Datex2Connector:
    return Datex2Connector(
        connector_type=Datex2Connector.ConnectorType(elem["connectorType"]["value"]),
        max_power=elem["maxPowerAtSocket"],
    )


def parse_refill_point(elem) -> Datex2RefillPoint:
    return Datex2RefillPoint(
        # external_identifier=
        id=elem["idG"],
        connectors=[parse_connector(connector) for connector in elem["connector"]],
    )


def parse_address(address_lines: list) -> str:
    if "order" in address_lines[0]:
        address_lines = sorted(address_lines, key=lambda line: line["order"])
    texts = []
    for line in address_lines:
        text = line["text"]
        texts.append(parse_multilingual_string(text).first())

    return " ".join(texts)


def parse_energy_infrastructure_site(
    elem: dict,
) -> Optional[Datex2EnergyInfrastructureSite]:
    operator = (
        elem["operator"]["afacAnOrganisation"]
        if "operator" in elem
        else elem["energyInfrastructureStation"][0]["operator"]["afacOrganisation"]
    )

    if "locationReference" in elem:
        location_reference = elem["locationReference"]
    else:
        location_reference = elem["energyInfrastructureStation"][0]["locationReference"]
    if (
        "locPointLocation" in location_reference
        or "locAreaLocation" in location_reference
    ):
        location = (
            location_reference["locPointLocation"]
            if "locPointLocation" in location_reference
            else location_reference["locAreaLocation"]
        )
        location_extension = location["locLocationExtensionG"]
        facility_location = (
            location_extension["facilityLocation"]
            if "facilityLocation" in location_extension
            else location_extension["FacilityLocation"]
        )
        address = facility_location["address"]
        city = address["city"]
        if "value" in city:
            city = city["value"][0]
    else:
        address = None

    refill_points = []
    if not "energyInfrastructureStation" in elem:
        return None

    for station in elem["energyInfrastructureStation"]:
        for refill_point in station["refillPoint"]:
            refill_points.append(
                parse_refill_point(refill_point["aegiElectricChargingPoint"])
            )

    area_location = (
        location_reference["locAreaLocation"]
        if "locAreaLocation" in location_reference
        else location_reference["locPointLocation"]
    )
    coordinates = parse_point_coordinates(area_location["coordinatesForDisplay"])

    return Datex2EnergyInfrastructureSite(
        id=elem["idG"],
        name=parse_multilingual_string(elem["name"]) if "name" in elem else None,
        additional_information=(
            parse_multilingual_string(elem["additionalInformation"][0])
            if "additionalInformation" in elem
            else None
        ),
        location=coordinates,
        zipcode=address["postcode"] if address and "postcode" in address else None,
        city=parse_multilingual_string(city).first() if address else None,
        street=parse_address(address["addressLine"]),
        country=address["countryCode"] if address else "DE",
        operator_name=parse_multilingual_string(operator["name"]),
        refill_points=refill_points,
        operator_phone=None,
    )


def parse_refill_point_status(
    elem: dict, last_updated: datetime.datetime = None, default_timezone=None
) -> Datex2RefillPointStatus:
    if "lastUpdated" in elem:
        last_updated = parse_datetime(elem["lastUpdated"], default_timezone)
    return Datex2RefillPointStatus(
        refill_point_id=elem["reference"]["idG"],
        last_updated=last_updated,
        status=Datex2RefillPointStatus.Status(elem["status"]["value"]),
    )


def parse_energy_infrastructure_site_status(
    elem: dict, default_timezone=None
) -> Datex2EnergyInfrastructureSiteStatus:
    last_updated = parse_datetime(elem.get("lastUpdated"), default_timezone)
    return Datex2EnergyInfrastructureSiteStatus(
        site_id=elem["reference"]["idG"],
        refill_point_statuses=[
            parse_refill_point_status(
                rp["aegiRefillPointStatus"], last_updated, default_timezone
            )
            for station in elem["energyInfrastructureStationStatus"]
            for rp in station["refillPointStatus"]
        ],
    )


class Datex2JsonParser:
    def parse(self, data) -> Iterable[Datex2EnergyInfrastructureSite]:
        root = json.loads(data)
        root = root["payload"]

        for table in root["aegiEnergyInfrastructureTablePublication"][
            "energyInfrastructureTable"
        ]:
            for site in tqdm(table["energyInfrastructureSite"]):
                site = parse_energy_infrastructure_site(site)
                if site is not None:
                    yield site

    def parse_status(
        self, data, station_as_site=False, default_timezone=None
    ) -> Iterable[Datex2EnergyInfrastructureSiteStatus]:
        if station_as_site:
            raise NotImplementedError()

        root = json.loads(data)
        root = root["messageContainer"]["payload"]

        for payload in root:
            for site in payload["aegiEnergyInfrastructureStatusPublication"][
                "energyInfrastructureSiteStatus"
            ]:
                yield parse_energy_infrastructure_site_status(site, default_timezone)
