import os

import requests
from django.core.management import BaseCommand

from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.sync import sync_chargers

API_URL = "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-table-publication"
SOURCE = "e-control_austria"


class Command(BaseCommand):
    help = "Connects to E-Control API to extract static charger information for Austria"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        root = get_econtrol_data()
        sites_datex = Datex2XmlParser().parse(root)
        sync_chargers(SOURCE, (site.convert(SOURCE) for site in sites_datex))


def get_econtrol_data():
    response = requests.get(
        API_URL,
        headers={
            "Accept": "application/xml",
            "Apikey": os.environ["ECONTROL_API_KEY"],
            "Referer": "https://ev-map.app",
        },
    )
    return response.text
