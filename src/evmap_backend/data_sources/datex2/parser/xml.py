import datetime
from typing import Iterable, Optional, Tuple
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from tqdm import tqdm

from evmap_backend.data_sources.datex2.parser import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
    Datex2EnergyInfrastructureSiteStatus,
    Datex2MultilingualString,
    Datex2RefillPoint,
    Datex2RefillPointStatus,
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


def find_payload(root: Element) -> Element:
    if root.tag not in [tag("con:payload"), tag("d2p:payload")]:
        if (result := root.find("con:payload", ns)) is not None:
            root = result
        elif (result := root.find("d2p:payload", ns)) is not None:
            root = result
        else:
            raise ValueError("payload not found")
    return root


def parse_multilingual_string(elem: Element) -> Optional[Datex2MultilingualString]:
    values_elem = elem.find("com:values", ns)
    values = {}
    if values_elem is not None:
        for value in values_elem.findall("com:value", ns):
            values[value.attrib["lang"]] = value.text

    return Datex2MultilingualString(values=values)


def parse_single_or_multilingual_string(elem: Element) -> Optional[str]:
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


def parse_energy_infrastructure_site_status(
    elem: Element,
) -> Datex2EnergyInfrastructureSiteStatus:
    last_updated_elem = elem.find("fac:lastUpdated", ns)
    last_updated = (
        datetime.datetime.fromisoformat(last_updated_elem.text)
        if last_updated_elem
        else None
    )
    return Datex2EnergyInfrastructureSiteStatus(
        site_id=elem.find("fac:reference", ns).attrib["id"],
        refill_point_statuses=[
            parse_refill_point_status(refill_point, last_updated)
            for station in elem.findall("egi:energyInfrastructureStationStatus", ns)
            for refill_point in station.findall("egi:refillPointStatus", ns)
        ],
    )


def parse_energy_infrastructure_station_status(
    elem: Element,
) -> Datex2EnergyInfrastructureSiteStatus:
    last_updated_elem = elem.find("fac:lastUpdated", ns)
    last_updated = (
        datetime.datetime.fromisoformat(last_updated_elem.text)
        if last_updated_elem
        else None
    )
    return Datex2EnergyInfrastructureSiteStatus(
        site_id=elem.find("fac:reference", ns).attrib["id"],
        refill_point_statuses=[
            parse_refill_point_status(refill_point, last_updated)
            for refill_point in elem.findall("egi:refillPointStatus", ns)
        ],
    )


def parse_refill_point_status(
    elem: Element, last_updated: datetime.datetime = None
) -> Datex2RefillPointStatus:
    last_updated_elem = elem.find("fac:lastUpdated", ns)
    if last_updated_elem is not None:
        last_updated = datetime.datetime.fromisoformat(last_updated_elem.text)
    return Datex2RefillPointStatus(
        refill_point_id=elem.find("fac:reference", ns).attrib["id"],
        last_updated=last_updated,
        status=Datex2RefillPointStatus.Status(elem.find("egi:status", ns).text),
    )


def parse_address(address: Element) -> str:
    address_lines = address.findall("locx:addressLine", ns)
    address_lines = sorted(address_lines, key=lambda line: int(line.attrib["order"]))
    texts = []
    for line in address_lines:
        text = line.find("locx:text", ns)
        text = parse_single_or_multilingual_string(text)
        if text is not None:
            texts.append(text)

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
        root = find_payload(root)

        for table in root.findall("egi:energyInfrastructureTable", ns):
            for site in tqdm(table.findall("egi:energyInfrastructureSite", ns)):
                yield parse_energy_infrastructure_site(site)

    def parse_status(
        self, xml, station_as_site=False
    ) -> Iterable[Datex2EnergyInfrastructureSiteStatus]:
        root = ElementTree.fromstring(xml)
        root = find_payload(root)

        for site in root.findall("egi:energyInfrastructureSiteStatus", ns):
            if station_as_site:
                for station in site.findall(
                    "egi:energyInfrastructureStationStatus", ns
                ):
                    yield parse_energy_infrastructure_station_status(station)
            else:
                yield parse_energy_infrastructure_site_status(site)
