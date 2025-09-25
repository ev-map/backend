import os

import requests
from defusedxml import ElementTree
from django.core.management import BaseCommand

from evmap_backend.data_sources.datex2.parser import parse_datex2_data

API_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription"
SOURCE = "mobilithek_ecomovement"


class Command(BaseCommand):
    help = "Connects to Mobilithek API to extract static charger information for Germany provided by Eco-Movement"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        root = get_mobilithek_data()
        parse_datex2_data(root, SOURCE)


def get_mobilithek_data():
    response = requests.get(
        API_URL,
        params={
            "subscriptionID": os.environ[
                "MOBILITHEK_ECOMOVEMENT_STATIC_SUBSCRIPTION_ID"
            ],
        },
        cert=os.environ["MOBILITHEK_CERTIFICATE"],
    )
    return ElementTree.fromstring(response.text)
