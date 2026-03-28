import datetime
import json
from typing import Iterable, Optional, Tuple

from django.core.exceptions import ValidationError
from tqdm import tqdm

from evmap_backend.chargers.fields import EVSEIDType, normalize_evseid, validate_evseid
from evmap_backend.data_sources.datex2.parser import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
    Datex2EnergyInfrastructureSiteStatus,
    Datex2MultilingualString,
    Datex2RefillPoint,
    Datex2RefillPointStatus,
    parse_datetime,
)


def get_alternatives(obj: dict, keys: Iterable[str]):
    for key in keys:
        if key in obj:
            return obj[key]
    return None


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
        max_power=elem["maxPowerAtSocket"] if "maxPowerAtSocket" in elem else None,
    )


def parse_refill_point(elem) -> Datex2RefillPoint:
    if "externalIdentifier" in elem:
        if isinstance(elem["externalIdentifier"], str):
            external_identifier = elem["externalIdentifier"]
        else:
            external_identifier = next(
                extid["identifier"]
                for extid in elem["externalIdentifier"]
                if extid["typeOfIdentifier"]["extendedValueG"] == "evseId"
            )
    else:
        external_identifier = None

    return Datex2RefillPoint(
        external_identifier=external_identifier,
        name=parse_multilingual_string(elem["name"]) if "name" in elem else None,
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
    elem: dict, station_as_chargepoint=False
) -> Optional[Datex2EnergyInfrastructureSite]:
    if "operator" in elem:
        operator = elem["operator"]
    elif "operator" in elem["energyInfrastructureStation"][0]:
        operator = elem["energyInfrastructureStation"][0]["operator"]
    else:
        operator = None
    if operator is not None:
        if isinstance(operator, list):
            operator = operator[0]
        operator = get_alternatives(
            operator,
            ["afacAnOrganisation", "afacOrganisation", "facOrganisationSpecification"],
        )
        operator = get_alternatives(operator, ["name", "organisationName"])

    if "locationReference" in elem:
        location_reference = elem["locationReference"]
    else:
        location_reference = elem["energyInfrastructureStation"][0]["locationReference"]

    address = None
    city = None

    location = get_alternatives(
        location_reference, ["locPointLocation", "locAreaLocation"]
    )
    if location is not None and "locLocationExtensionG" in location:
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

    refill_points = []
    if not "energyInfrastructureStation" in elem:
        return None

    for station in elem["energyInfrastructureStation"]:
        station_refill_points = [
            parse_refill_point(
                get_alternatives(
                    refill_point,
                    ["aegiElectricChargingPoint", "egiElectricChargingPoint"],
                )
            )
            for refill_point in station["refillPoint"]
        ]

        if station_as_chargepoint:
            # In some sources, EVSEs are incorrectly mapped as energyInfrastructureStation
            station_id = station["idG"]
            evseid = normalize_evseid(station_id)
            validate_evseid(evseid, EVSEIDType.EVSE)
            refill_points.append(
                Datex2RefillPoint(
                    id=station_id,
                    external_identifier=evseid,
                    connectors=[
                        con for rp in station_refill_points for con in rp.connectors
                    ],
                )
            )
        else:
            refill_points += station_refill_points

    area_location = get_alternatives(
        location_reference, ["locAreaLocation", "locPointLocation"]
    )
    coordinates = (
        area_location["coordinatesForDisplay"]
        if "coordinatesForDisplay" in area_location
        else area_location["pointByCoordinates"]["pointCoordinates"]
    )
    coordinates = parse_point_coordinates(coordinates)

    return Datex2EnergyInfrastructureSite(
        id=elem["idG"],
        name=parse_multilingual_string(elem["name"]) if "name" in elem else None,
        additional_information=(
            parse_multilingual_string(elem["additionalInformation"][0])
            if "additionalInformation" in elem
            and len(elem["additionalInformation"]) > 0
            else None
        ),
        location=coordinates,
        zipcode=address["postcode"] if address and "postcode" in address else None,
        city=parse_multilingual_string(city).first() if city else None,
        street=parse_address(address["addressLine"]) if address else None,
        country=address["countryCode"] if address else None,
        operator_name=(
            parse_multilingual_string(operator) if operator is not None else None
        ),
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
                get_alternatives(
                    rp, ["aegiRefillPointStatus", "aegiElectricChargingPointStatus"]
                ),
                last_updated,
                default_timezone,
            )
            for station in elem["energyInfrastructureStationStatus"]
            for rp in station["refillPointStatus"]
        ],
    )


class Datex2JsonParser:
    def __init__(self, station_as_chargepoint=False):
        self.station_as_chargepoint = station_as_chargepoint

    def parse(self, data) -> Iterable[Datex2EnergyInfrastructureSite]:
        root = json.loads(data)
        root = root["payload"]

        if isinstance(root, list):
            root = root[0]

        root = get_alternatives(
            root,
            [
                "aegiEnergyInfrastructureTablePublication",
                "egiEnergyInfrastructureTablePublication",
            ],
        )
        for table in root["energyInfrastructureTable"]:
            for site in tqdm(table["energyInfrastructureSite"]):
                site = parse_energy_infrastructure_site(
                    site, self.station_as_chargepoint
                )
                if site is not None:
                    yield site

    def parse_status(
        self, data, default_timezone=None
    ) -> Iterable[Datex2EnergyInfrastructureSiteStatus]:
        root = json.loads(data)
        root = root["messageContainer"]["payload"]

        for payload in root:
            for site in payload["aegiEnergyInfrastructureStatusPublication"][
                "energyInfrastructureSiteStatus"
            ]:
                yield parse_energy_infrastructure_site_status(site, default_timezone)
