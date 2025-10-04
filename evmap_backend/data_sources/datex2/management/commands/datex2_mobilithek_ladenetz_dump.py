import os

import requests
from django.core.management import BaseCommand

from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.data_sources.datex2.sync import sync_chargers

API_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription"
SOURCE = "mobilithek_ladenetz"


class Command(BaseCommand):
    help = "Connects to Mobilithek API to extract static charger information for Germany provided by Ladenetz"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        root = get_mobilithek_data()
        sites_datex = Datex2XmlParser().parse(root)
        sync_chargers(sites_datex, SOURCE)


def get_mobilithek_data():
    response = requests.get(
        API_URL,
        params={
            "subscriptionID": os.environ["MOBILITHEK_LADENETZ_STATIC_SUBSCRIPTION_ID"],
        },
        cert=os.environ["MOBILITHEK_CERTIFICATE"],
    )
    response.encoding = response.apparent_encoding
    return response.text
