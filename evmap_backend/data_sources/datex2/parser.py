from xml.etree.ElementTree import Element

from django.contrib.gis.geos import Point
from django.db import transaction
from tqdm import tqdm

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector

ns = {
    "d2p": "http://datex2.eu/schema/3/d2Payload",
    "com": "http://datex2.eu/schema/3/common",
    "con": "http://datex2.eu/schema/3/messageContainer",
    "egi": "http://datex2.eu/schema/3/energyInfrastructure",
    "loc": "http://datex2.eu/schema/3/locationReferencing",
    "locx": "http://datex2.eu/schema/3/locationExtension",
    "fac": "http://datex2.eu/schema/3/facilities",
}

connectors = {
    "chademo": Connector.ConnectorTypes.CHADEMO,
    "cee3": Connector.ConnectorTypes.OTHER,
    "cee5": Connector.ConnectorTypes.OTHER,
    "yazaki": Connector.ConnectorTypes.OTHER,
    "domestic": Connector.ConnectorTypes.OTHER,
    "domesticA": Connector.ConnectorTypes.OTHER,
    "domesticB": Connector.ConnectorTypes.OTHER,
    "domesticC": Connector.ConnectorTypes.OTHER,
    "domesticD": Connector.ConnectorTypes.OTHER,
    "domesticE": Connector.ConnectorTypes.OTHER,
    "domesticF": Connector.ConnectorTypes.SCHUKO,
    "domesticG": Connector.ConnectorTypes.OTHER,
    "domesticH": Connector.ConnectorTypes.OTHER,
    "domesticI": Connector.ConnectorTypes.OTHER,
    "domesticJ": Connector.ConnectorTypes.OTHER,
    "domesticK": Connector.ConnectorTypes.OTHER,
    "domesticL": Connector.ConnectorTypes.OTHER,
    "domesticM": Connector.ConnectorTypes.OTHER,
    "domesticN": Connector.ConnectorTypes.OTHER,
    "domesticO": Connector.ConnectorTypes.OTHER,
    "iec60309x2single16": Connector.ConnectorTypes.CEE_SINGLE_16,
    "iec60309x2three16": Connector.ConnectorTypes.CEE_THREE_16,
    "iec60309x2three32": Connector.ConnectorTypes.CEE_THREE_32,
    "iec60309x2three64": Connector.ConnectorTypes.CEE_THREE_64,
    "iec62196T1": Connector.ConnectorTypes.TYPE_1,
    "iec62196T1COMBO": Connector.ConnectorTypes.CCS_TYPE_1,
    "iec62196T2": Connector.ConnectorTypes.TYPE_2,
    "iec62196T2COMBO": Connector.ConnectorTypes.CCS_TYPE_2,
    "iec62196T3A": Connector.ConnectorTypes.TYPE_3A,
    "iec62196T3C": Connector.ConnectorTypes.TYPE_3C,
    "pantographBottomUp": Connector.ConnectorTypes.OTHER,
    "pantographTopDown": Connector.ConnectorTypes.OTHER,
    "teslaConnectorEurope": Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
    "teslaConnectorAmerica": Connector.ConnectorTypes.NACS,
    "teslaR": Connector.ConnectorTypes.TESLA_ROADSTER_HPC,
    "teslaS": Connector.ConnectorTypes.OTHER,
    "other": Connector.ConnectorTypes.OTHER,
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


def parse_connector(elem, chargepoint: Chargepoint):
    Connector(
        chargepoint=chargepoint,
        connector_type=connectors[elem.find("egi:connectorType", ns).text],
        max_power=float(elem.find("egi:maxPowerAtSocket", ns).text),
    ).save()


def parse_refill_point(elem: Element, site: ChargingSite):
    point = Chargepoint(
        site=site,
        evseid=text_if_exists(elem, "fac:externalIdentifier"),
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
    # phone = text_if_exists(contactInfo, "fac:telephoneNumber")

    site, created = ChargingSite.objects.update_or_create(
        data_source=source,
        id_from_source=elem.attrib["id"],
        defaults=dict(
            name=parse_multilingual_string(elem.find("fac:name", ns)),
            location=parse_point_coordinates(
                elem.find("fac:locationReference", ns)
                .find("loc:pointByCoordinates", ns)
                .find("loc:pointCoordinates", ns)
            ),
            operator=parse_multilingual_string(operator.find("fac:name", ns)),
            # operatorPhone=phone,
        ),
    )
    Chargepoint.objects.filter(site=site).delete()
    for station in elem.findall("egi:energyInfrastructureStation", ns):
        for refill_point in station.findall("egi:refillPoint", ns):
            parse_refill_point(refill_point, site=site)
