import json
from typing import Iterable, Optional, Tuple

from defusedxml import ElementTree
from tqdm import tqdm

from evmap_backend.data_sources.datex2.parser import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
    Datex2MultilingualString,
    Datex2RefillPoint,
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
    address_lines = sorted(address_lines, key=lambda line: line["order"])
    texts = []
    for line in address_lines:
        text = line["text"]
        texts.append(parse_multilingual_string(text).first())

    return " ".join(texts)


def parse_energy_infrastructure_site(
    elem: dict,
) -> Optional[Datex2EnergyInfrastructureSite]:
    operator = elem["operator"]["afacAnOrganisation"]

    refill_points = []
    if not "energyInfrastructureStation" in elem:
        return None

    for station in elem["energyInfrastructureStation"]:
        for refill_point in station["refillPoint"]:
            refill_points.append(
                parse_refill_point(refill_point["aegiElectricChargingPoint"])
            )

    address = elem["locationReference"]["locPointLocation"]["locLocationExtensionG"][
        "facilityLocation"
    ]["address"]
    return Datex2EnergyInfrastructureSite(
        id=elem["idG"],
        name=parse_multilingual_string(elem["name"]) if "name" in elem else None,
        additional_information=parse_multilingual_string(
            elem["additionalInformation"][0]
        ),
        location=parse_point_coordinates(
            elem["locationReference"]["locAreaLocation"]["coordinatesForDisplay"]
        ),
        zipcode=address["postcode"],
        city=parse_multilingual_string(address["city"]["value"][0]).first(),
        street=parse_address(address["addressLine"]),
        country=address["countryCode"],
        operator_name=parse_multilingual_string(operator["name"]),
        refill_points=refill_points,
        operator_phone=None,
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
