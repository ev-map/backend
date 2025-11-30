import os

import requests
from django.contrib.gis.geos import Point
from django.core.management import BaseCommand
from django.db import transaction

from evmap_backend.data_sources.goingelectric.models import (
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
)

API_URL = "https://api.goingelectric.de"


class Command(BaseCommand):
    help = "Connects to GoingElectric API to extract static charger information"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        startkey = None
        while True:
            response = get_goingelectric_chargers(startkey=startkey)

            if response["status"] != "ok":
                raise RuntimeError("error getting data from GoingElectric API")

            for data in response["chargelocations"]:
                with transaction.atomic():
                    location, created = (
                        GoingElectricChargeLocation.objects.update_or_create(
                            id=data["ge_id"],
                            name=data["name"],
                            coordinates=Point(
                                data["coordinates"]["lng"], data["coordinates"]["lat"]
                            ),
                            address_city=(
                                data["address"]["city"]
                                if data["address"]["city"]
                                else ""
                            ),
                            address_country=(
                                data["address"]["country"]
                                if data["address"]["country"]
                                else ""
                            ),
                            address_postcode=(
                                data["address"]["postcode"]
                                if data["address"]["postcode"]
                                else ""
                            ),
                            address_street=(
                                data["address"]["street"]
                                if data["address"]["street"]
                                else ""
                            ),
                            network=data["network"] if data["network"] else "",
                            url=data["url"],
                            fault_report=data["fault_report"],
                            verified=data["verified"],
                        )
                    )
                    GoingElectricChargepoint.objects.filter(
                        chargelocation=location
                    ).delete()
                    for chargepoint in data["chargepoints"]:
                        GoingElectricChargepoint.objects.create(
                            chargelocation=location,
                            type=chargepoint["type"],
                            power=chargepoint["power"],
                            count=chargepoint["count"],
                        )

            if "startkey" in response:
                startkey = response["startkey"]
                print(startkey)
            else:
                break


def get_goingelectric_chargers(startkey=None):
    params = {
        "clustering": False,
        "key": os.environ["GOINGELECTRIC_API_KEY"],
        "ne_lat": 90.0,
        "ne_lng": 180.0,
        "sw_lat": -90.0,
        "sw_lng": -180.0,
    }
    if startkey is not None:
        params["startkey"] = startkey
    response = requests.get(
        API_URL + "/chargepoints",
        params=params,
        headers={
            "Referer": "https://www.goingelectric.de/",
            "Origin": "https://www.goingelectric.de",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        },
    )
    return response.json()
