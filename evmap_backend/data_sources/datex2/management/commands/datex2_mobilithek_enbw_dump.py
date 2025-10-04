import os

import requests
from django.core.management import BaseCommand

from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.sync import sync_chargers

API_URL = "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription"
SOURCE = "mobilithek_enbw"


class Command(BaseCommand):
    help = "Connects to Mobilithek API to extract static charger information for Germany provided by EnBW"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        root = get_mobilithek_data()
        sites_datex = Datex2JsonParser().parse(root)
        sync_chargers(SOURCE, (site.convert(SOURCE) for site in sites_datex))


def get_mobilithek_data():
    response = requests.get(
        API_URL,
        params={
            "subscriptionID": os.environ["MOBILITHEK_ENBW_STATIC_SUBSCRIPTION_ID"],
        },
        cert=os.environ["MOBILITHEK_CERTIFICATE"],
    )
    response.encoding = response.apparent_encoding
    return response.text
