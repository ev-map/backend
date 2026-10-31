import datetime
import re
from collections.abc import Iterable
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
    parse_datetime,
)

ns = {
    "d2p": "http://datex2.eu/schema/3/d2Payload",
    "com": "http://datex2.eu/schema/3/common",
    "con": "http://datex2.eu/schema/3/messageContainer",
    "egi": "http://datex2.eu/schema/3/energyInfrastructure",
    "aegi": "http://datex2.eu/schema/3/afirEnergyInfrastructure",
    "loc": "http://datex2.eu/schema/3/locationReferencing",
    "locx": "http://datex2.eu/schema/3/locationExtension",
    "fac": "http://datex2.eu/schema/3/facilities",
    "afac": "http://datex2.eu/schema/3/afirFacilities",
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
    if root.tag not in [
        tag("con:payload"),
        tag("d2p:payload"),
        tag("egi:EnergyInfrastructureTablePublication"),
        tag("egi:EnergyInfrastructureStatusPublication"),
    ]:
        if (result := root.find("con:payload", ns)) is not None or (
            result := root.find("d2p:payload", ns)
        ) is not None:
            root = result
        else:
            raise ValueError("payload not found")
    return root


def parse_multilingual_string(elem: Element | None) -> Datex2MultilingualString | None:
    if elem is None:
        return None

    values_elem = elem.find("com:values", ns)
    values = {}
    if values_elem is not None:
        for value in values_elem.findall("com:value", ns):
            values[value.attrib["lang"]] = value.text

    return Datex2MultilingualString(values=values)


def parse_single_or_multilingual_string(elem: Element) -> str | None:
    if elem.text is not None and elem.text.strip() != "":
        return elem.text
    else:
        return parse_multilingual_string(elem).first()


def parse_point_coordinates(elem: Element) -> tuple[float, float]:
    return (
        float(elem.find("loc:longitude", ns).text),
        float(elem.find("loc:latitude", ns).text),
    )


def parse_connector(elem) -> Datex2Connector:
    charging_mode = find_alternatives(elem, ["egi:chargingMode", "aegi:chargingMode"])
    return Datex2Connector(
        connector_type=Datex2Connector.ConnectorType(
            find_alternatives(elem, ["egi:connectorType", "aegi:connectorType"]).text
        ),
        charging_mode=(
            Datex2Connector.ChargingMode(charging_mode.text)
            if charging_mode is not None
            else None
        ),
        max_power=float(
            find_alternatives(
                elem, ["egi:maxPowerAtSocket", "aegi:maxPowerAtSocket"]
            ).text
        ),
    )


def parse_refill_point(elem: Element) -> Datex2RefillPoint:
    name = elem.find("fac:name", ns)
    connectors = findall_alternatives(elem, ["egi:connector", "aegi:connector"])
    external_identifier = elem.find("fac:externalIdentifier", ns)
    if external_identifier is None and len(connectors) == 1:
        external_identifier = (
            connectors[0]
            .find("aegi:externalIdentifier", ns)
            .find("afac:identifier", ns)
        )

    return Datex2RefillPoint(
        external_identifier=external_identifier.text
        if external_identifier is not None
        else None,
        id=elem.attrib["id"],
        connectors=[parse_connector(connector) for connector in connectors],
        name=parse_multilingual_string(name) if name is not None else None,
    )


def parse_energy_infrastructure_site_status(
    elem: Element,
    default_timezone=None,
) -> Datex2EnergyInfrastructureSiteStatus:
    last_updated_elem = find_alternatives(elem, ["fac:lastUpdated", "afac:lastUpdated"])
    last_updated = (
        parse_datetime(last_updated_elem.text, default_timezone)
        if last_updated_elem
        else None
    )
    return Datex2EnergyInfrastructureSiteStatus(
        site_id=find_alternatives(elem, ["fac:reference", "afac:reference"]).attrib[
            "id"
        ],
        refill_point_statuses=[
            parse_refill_point_status(refill_point, last_updated, default_timezone)
            for station in findall_alternatives(
                elem,
                [
                    "egi:energyInfrastructureStationStatus",
                    "aegi:energyInfrastructureStationStatus",
                ],
            )
            for refill_point in findall_alternatives(
                station, ["egi:refillPointStatus", "aegi:refillPointStatus"]
            )
        ],
    )


def parse_energy_infrastructure_station_status(
    elem: Element,
    default_timezone=None,
) -> Datex2EnergyInfrastructureSiteStatus:
    last_updated_elem = find_alternatives(elem, ["fac:lastUpdated", "afac:lastUpdated"])
    last_updated = (
        parse_datetime(last_updated_elem.text, default_timezone)
        if last_updated_elem
        else None
    )
    return Datex2EnergyInfrastructureSiteStatus(
        site_id=find_alternatives(elem, ["fac:reference", "afac:reference"]).attrib[
            "id"
        ],
        refill_point_statuses=[
            parse_refill_point_status(refill_point, last_updated, default_timezone)
            for refill_point in findall_alternatives(
                elem, ["egi:refillPointStatus", "aegi:refillPointStatus"]
            )
        ],
    )


def parse_refill_point_status(
    elem: Element, last_updated: datetime.datetime | None = None, default_timezone=None
) -> Datex2RefillPointStatus:
    last_updated_elem = find_alternatives(elem, ["fac:lastUpdated", "afac:lastUpdated"])
    if last_updated_elem is not None:
        last_updated = parse_datetime(last_updated_elem.text, default_timezone)
    return Datex2RefillPointStatus(
        refill_point_id=find_alternatives(
            elem, ["fac:reference", "afac:reference"]
        ).attrib["id"],
        last_updated=last_updated,
        status=Datex2RefillPointStatus.Status(
            find_alternatives(elem, ["egi:status", "aegi:status"]).text
        ),
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


def find_alternatives(elem: Element, tags: Iterable[str]):
    if elem is None:
        return None
    for tag in tags:
        if (subelem := elem.find(tag, ns)) is not None:
            return subelem
    return None


def findall_alternatives(elem: Element, tags: Iterable[str]):
    if elem is None:
        return []

    results = []
    for tag in tags:
        results += elem.findall(tag, ns)
    return results


def parse_energy_infrastructure_site(elem: Element) -> Datex2EnergyInfrastructureSite:
    stations = findall_alternatives(
        elem, ["egi:energyInfrastructureStation", "aegi:energyInfrastructureStation"]
    )

    operator = find_alternatives(elem, ["fac:operator", "egi:energyProvider"])
    if operator is None:
        operator = find_alternatives(
            stations[0], ["fac:operator", "egi:energyProvider"]
        )
    if operator is not None:
        org_unit = operator.find("fac:organisationUnit", ns)
        contactInfo = (
            org_unit.find("fac:contactInformation", ns)
            if org_unit is not None
            else None
        )
        phone = (
            text_if_exists(contactInfo, "fac:telephoneNumber")
            if contactInfo is not None
            else text_if_exists(operator, "fac:telephoneNumber")
        )
    else:
        phone = None

    refill_points = []
    for station in stations:
        for refill_point in findall_alternatives(
            station, ["egi:refillPoint", "aegi:refillPoint"]
        ):
            refill_points.append(parse_refill_point(refill_point))

    location = find_alternatives(elem, ["fac:locationReference", "aegi:entrance"])
    loc_extension = find_alternatives(
        location,
        [
            "loc:_pointLocationExtension",
            "loc:_locationReferenceExtension",
            "loc:_locationExtension",
        ],
    )
    facility_location = find_alternatives(
        loc_extension,
        ["loc:facilityLocation", "locx:facilityLocation", "loc:afirFacilityLocation"],
    )
    address = find_alternatives(facility_location, ["locx:address", "afac:address"])
    point_by_coordinates = location.find("loc:pointByCoordinates", ns)
    if point_by_coordinates is not None:
        point_coordinates = point_by_coordinates.find("loc:pointCoordinates", ns)
    else:
        point_coordinates = location.find("loc:coordinatesForDisplay", ns)
    city = address.find("locx:city", ns)
    country_code = address.find("locx:countryCode", ns)
    return Datex2EnergyInfrastructureSite(
        id=elem.attrib["id"],
        name=parse_multilingual_string(elem.find("fac:name", ns)),
        description=None,
        location=parse_point_coordinates(point_coordinates),
        zipcode=address.find("locx:postcode", ns).text,
        city=parse_single_or_multilingual_string(city),
        street=parse_address(address),
        country=country_code.text if country_code is not None else None,
        operator_name=parse_multilingual_string(operator.find("fac:name", ns))
        if operator is not None
        else None,
        operator_phone=phone,
        refill_points=refill_points,
    )


class Datex2XmlParser:
    def __init__(self, realtime_station_as_site=False):
        self.realtime_station_as_site = realtime_station_as_site

    def parse(self, xml) -> Iterable[Datex2EnergyInfrastructureSite]:
        for http_ns in ns.values():
            # some sources use https instead of http, so we need to replace the namespace in the xml string
            https_ns = http_ns.replace("http", "https")
            xml = re.sub(f'xmlns:(\\w+)="{https_ns}"', f'xmlns:\\1="{http_ns}"', xml)
        root = ElementTree.fromstring(xml)
        root = find_payload(root)

        for table in findall_alternatives(
            root, ["egi:energyInfrastructureTable", "aegi:energyInfrastructureTable"]
        ):
            for site in tqdm(
                findall_alternatives(
                    table,
                    ["egi:energyInfrastructureSite", "aegi:energyInfrastructureSite"],
                ),
                disable=None,
            ):
                yield parse_energy_infrastructure_site(site)

    def parse_status(
        self, xml, default_timezone=None
    ) -> Iterable[Datex2EnergyInfrastructureSiteStatus]:
        root = ElementTree.fromstring(xml)
        root = find_payload(root)

        for site in findall_alternatives(
            root,
            [
                "egi:energyInfrastructureSiteStatus",
                "aegi:energyInfrastructureSiteStatus",
            ],
        ):
            if self.realtime_station_as_site:
                for station in findall_alternatives(
                    site,
                    [
                        "egi:energyInfrastructureStationStatus",
                        "aegi:energyInfrastructureStationStatus",
                    ],
                    ns,
                ):
                    yield parse_energy_infrastructure_station_status(
                        station, default_timezone
                    )
            else:
                yield parse_energy_infrastructure_site_status(site, default_timezone)
