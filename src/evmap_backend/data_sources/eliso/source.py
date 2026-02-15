import os
from typing import Iterable, List, Tuple

import requests
from django.contrib.gis.geos import Point
from tqdm import tqdm

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.sync import sync_chargers

API_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription"

connector_mapping = {
    "Type 2 (AC)": Connector.ConnectorTypes.TYPE_2,
    "Combo2/CCS (DC)": Connector.ConnectorTypes.CCS_TYPE_2,
}


def parse_eliso_chargers(
    root, source, license_attribution
) -> Iterable[Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]]:
    for item in tqdm(root):
        # Eliso doesn't have IDs, so we make one from the city and address:
        item_id = item["address"] + " " + item["postalCode"] + " " + item["city"]

        site = ChargingSite(
            data_source=source,
            license_attribution=license_attribution,
            id_from_source=item_id,
            name=item["address"],
            street=item["address"],
            zipcode=item["postalCode"],
            city=item["city"],
            country=item["country_iso_3166_alpha_2"],
            network=Network.objects.get_or_create(
                evse_operator_id=item["operator"],
                defaults=dict(name=item["operator_name"]),
            )[0],
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


class ElisoDataSource(DataSource):
    id = "mobilithek_eliso"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "eliso GmbH"
    # https://mobilithek.info/offers/843477276990078976

    def pull_data(self):
        root = get_mobilithek_data()
        eliso_chargers = parse_eliso_chargers(root, self.id, self.license_attribution)
        sync_chargers(self.id, eliso_chargers)
