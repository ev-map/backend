from typing import Iterable, Tuple
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from tqdm import tqdm

from evmap_backend.data_sources.datex2.parser import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
    Datex2MultilingualString,
    Datex2RefillPoint,
)

ns = {
    "d2p": "http://datex2.eu/schema/3/d2Payload",
    "com": "http://datex2.eu/schema/3/common",
    "con": "http://datex2.eu/schema/3/messageContainer",
    "egi": "http://datex2.eu/schema/3/energyInfrastructure",
    "loc": "http://datex2.eu/schema/3/locationReferencing",
    "locx": "http://datex2.eu/schema/3/locationExtension",
    "fac": "http://datex2.eu/schema/3/facilities",
}


def tag(qname: str):
    namespace, tag = qname.split(":", 1)
    return f"{{{ns[namespace]}}}{tag}"


def text_if_exists(elem: Element, tag: str):
    found = elem.find(tag, ns)
    if found is not None:
        return found.text
    else:
        return None


def parse_multilingual_string(elem: Element) -> Datex2MultilingualString:
    values = {}
    for value in elem.find("com:values", ns).findall("com:value", ns):
        values[value.attrib["lang"]] = value.text

    return Datex2MultilingualString(values=values)


def parse_single_or_multilingual_string(elem: Element) -> str:
    if elem.text is not None:
        return elem.text
    else:
        return parse_multilingual_string(elem).first()


def parse_point_coordinates(elem: Element) -> Tuple[float, float]:
    return (
        float(elem.find("loc:longitude", ns).text),
        float(elem.find("loc:latitude", ns).text),
    )


def parse_connector(elem) -> Datex2Connector:
    charging_mode = text_if_exists(elem, "egi:chargingMode")
    return Datex2Connector(
        connector_type=Datex2Connector.ConnectorType(
            elem.find("egi:connectorType", ns).text
        ),
        charging_mode=(
            Datex2Connector.ChargingMode(charging_mode) if charging_mode else None
        ),
        max_power=float(elem.find("egi:maxPowerAtSocket", ns).text),
    )


def parse_refill_point(elem: Element) -> Datex2RefillPoint:
    return Datex2RefillPoint(
        external_identifier=text_if_exists(elem, "fac:externalIdentifier"),
        id=elem.attrib["id"],
        connectors=[
            parse_connector(connector)
            for connector in elem.findall("egi:connector", ns)
        ],
    )


def parse_address(address: Element) -> str:
    address_lines = address.findall("locx:addressLine", ns)
    address_lines = sorted(address_lines, key=lambda line: int(line.attrib["order"]))
    texts = []
    for line in address_lines:
        text = line.find("locx:text", ns)
        texts.append(parse_single_or_multilingual_string(text))

    return " ".join(texts)


def parse_energy_infrastructure_site(elem: Element) -> Datex2EnergyInfrastructureSite:
    operator = elem.find("fac:operator", ns)
    contactInfo = operator.find("fac:organisationUnit", ns).find(
        "fac:contactInformation", ns
    )
    phone = text_if_exists(contactInfo, "fac:telephoneNumber")

    refill_points = []
    for station in elem.findall("egi:energyInfrastructureStation", ns):
        for refill_point in station.findall("egi:refillPoint", ns):
            refill_points.append(parse_refill_point(refill_point))

    location = elem.find("fac:locationReference", ns)
    loc_extension = location.find("loc:_pointLocationExtension", ns)
    if loc_extension is None:
        loc_extension = location.find("loc:_locationReferenceExtension", ns)
        facility_location = loc_extension.find("loc:facilityLocation", ns)
    else:
        facility_location = loc_extension.find("locx:facilityLocation", ns)
    address = facility_location.find("locx:address", ns)
    return Datex2EnergyInfrastructureSite(
        id=elem.attrib["id"],
        name=parse_multilingual_string(elem.find("fac:name", ns)),
        location=parse_point_coordinates(
            location.find("loc:pointByCoordinates", ns).find("loc:pointCoordinates", ns)
        ),
        zipcode=address.find("locx:postcode", ns).text,
        city=parse_single_or_multilingual_string(address.find("locx:city", ns)),
        street=parse_address(address),
        country=address.find("locx:countryCode", ns).text,
        operator_name=parse_multilingual_string(operator.find("fac:name", ns)),
        operator_phone=phone,
        refill_points=refill_points,
    )


class Datex2XmlParser:
    def parse(self, xml) -> Iterable[Datex2EnergyInfrastructureSite]:
        root = ElementTree.fromstring(xml)

        if root.tag not in [tag("con:payload"), tag("d2p:payload")]:
            if (result := root.find("con:payload", ns)) is not None:
                root = result
            elif (result := root.find("d2p:payload", ns)) is not None:
                root = result
            else:
                raise ValueError("payload not found")

        for table in root.findall("egi:energyInfrastructureTable", ns):
            for site in tqdm(table.findall("egi:energyInfrastructureSite", ns)):
                yield parse_energy_infrastructure_site(site)
