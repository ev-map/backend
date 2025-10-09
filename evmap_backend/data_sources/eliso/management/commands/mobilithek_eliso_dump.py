import os
from typing import Iterable, List, Tuple

import requests
from django.contrib.gis.geos import Point
from django.core.management import BaseCommand
from tqdm import tqdm

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector
from evmap_backend.sync import sync_chargers

API_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription"
SOURCE = "mobilithek_eliso"


connector_mapping = {
    "Type 2 (AC)": Connector.ConnectorTypes.TYPE_2,
    "Combo2/CCS (DC)": Connector.ConnectorTypes.CCS_TYPE_2,
}


class Command(BaseCommand):
    help = "Connects to Mobilithek API to extract static charger information for Germany provided by Eliso"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        root = get_mobilithek_data()
        eliso_chargers = parse_eliso_chargers(root)
        sync_chargers(SOURCE, eliso_chargers)


def parse_eliso_chargers(
    root,
) -> Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]]:
    for item in tqdm(root):
        # Eliso doesn't have IDs, so we make one from the city and address:
        item_id = item["address"] + " " + item["postalCode"] + " " + item["city"]

        site = ChargingSite(
            data_source=SOURCE,
            id_from_source=item_id,
            name=item["address"],
            street=item["address"],
            zipcode=item["postalCode"],
            city=item["city"],
            country=item["country_iso_3166_alpha_2"],
            operator=item["operator_name"],
            location=Point(
                item["coordinates"]["longitude"], item["coordinates"]["latitude"]
            ),
        )

        chargepoints = []
        for evse in item["evses"]:
            chargepoint = Chargepoint(
                id_from_source=evse["evseId"],
                evseid=evse["evseId"],
            )
            connectors = [
                Connector(
                    connector_type=connector_mapping[connector["type_of_connector"]],
                    max_power=connector["maxPower"] * 1000,
                )
                for connector in evse["connectors"]
            ]
            chargepoints.append((chargepoint, connectors))
        yield site, chargepoints


def get_mobilithek_data():
    response = requests.get(
        API_URL,
        params={
            "subscriptionID": os.environ["MOBILITHEK_ELISO_STATIC_SUBSCRIPTION_ID"],
        },
        cert=os.environ["MOBILITHEK_CERTIFICATE"],
    )
    return response.json()
