from xml.etree.ElementTree import Element

from django.contrib.gis.geos import Point
from django.db import transaction
from tqdm import tqdm

from evmap_backend.data_sources.datex2.models import (
    Datex2Connector,
    Datex2EnergyInfrastructureSite,
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


def parse_datex2_data(elem: Element, source: str):
    if elem.tag not in [tag("con:payload"), tag("d2p:payload")]:
        if (result := elem.find("con:payload", ns)) is not None:
            elem = result
        elif (result := elem.find("d2p:payload", ns)) is not None:
            elem = result
        else:
            raise ValueError("payload not found")

    for table in elem.findall("egi:energyInfrastructureTable", ns):
        for site in tqdm(table.findall("egi:energyInfrastructureSite", ns)):
            with transaction.atomic():
                parse_energy_infrastructure_site(site, source)


def parse_multilingual_string(elem: Element) -> str:
    # TODO: this simply returns the first available value. We should rather parse to an I18nField.
    return elem.find("com:values", ns).find("com:value", ns).text


def parse_point_coordinates(elem: Element) -> Point:
    return Point(
        float(elem.find("loc:longitude", ns).text),
        float(elem.find("loc:latitude", ns).text),
    )


def text_if_exists(elem: Element, tag: str):
    found = elem.find(tag, ns)
    if found is not None:
        return found.text
    else:
        return ""


def parse_connector(elem, refill_point: Datex2RefillPoint):
    max_power = elem.find("egi:maxPowerAtSocket", ns).text
    try:
        max_power = int(max_power)
    except ValueError:
        max_power = int(float(max_power))

    Datex2Connector(
        refill_point=refill_point,
        connector_type=elem.find("egi:connectorType", ns).text,
        charging_mode=text_if_exists(elem, "egi:chargingMode"),
        max_power=max_power,
    ).save()


def parse_refill_point(elem: Element, site: Datex2EnergyInfrastructureSite):
    point = Datex2RefillPoint(
        site=site,
        externalIdentifier=text_if_exists(elem, "fac:externalIdentifier"),
        id_from_source=elem.attrib["id"],
    )
    point.save()
    for connector in elem.findall("egi:connector", ns):
        parse_connector(connector, point)


def parse_energy_infrastructure_site(elem: Element, source: str):
    operator = elem.find("fac:operator", ns)
    contactInfo = operator.find("fac:organisationUnit", ns).find(
        "fac:contactInformation", ns
    )

    phone = text_if_exists(contactInfo, "fac:telephoneNumber")
    site, created = Datex2EnergyInfrastructureSite.objects.update_or_create(
        source=source,
        id_from_source=elem.attrib["id"],
        defaults=dict(
            name=parse_multilingual_string(elem.find("fac:name", ns)),
            location=parse_point_coordinates(
                elem.find("fac:locationReference", ns)
                .find("loc:pointByCoordinates", ns)
                .find("loc:pointCoordinates", ns)
            ),
            operatorName=parse_multilingual_string(operator.find("fac:name", ns)),
            operatorPhone=phone,
        ),
    )
    Datex2RefillPoint.objects.filter(site=site).delete()
    for station in elem.findall("egi:energyInfrastructureStation", ns):
        for refill_point in station.findall("egi:refillPoint", ns):
            parse_refill_point(refill_point, site=site)
