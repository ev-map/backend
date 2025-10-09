import os

import requests
from django.core.management import BaseCommand

from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.sync import sync_chargers

API_URL = "https://api.eco-movement.com/api/nap/datexii/locations"
SOURCE = "luxembourg_ecomovement"


class Command(BaseCommand):
    help = "Connects to Eco-Movement API to extract static charger information for Luxembourg"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        root = get_ecomovement_data()
        sites_datex = Datex2XmlParser().parse(root)
        sync_chargers(SOURCE, (site.convert(SOURCE) for site in sites_datex))


def get_ecomovement_data():
    response = requests.get(
        API_URL,
        params={
            "token": os.environ["ECOMOVEMENT_LUXEMBOURG_TOKEN"],
        },
    )
    return response.text
