import os

import requests
from django.contrib.gis.geos import Point
from django.db import transaction

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.goingelectric.models import (
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
    GoingElectricNetwork,
)

API_URL = "https://api.goingelectric.de"


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


class GoingElectricDataSource(DataSource):
    id = "goingelectric"
    supported_update_methods = [UpdateMethod.PULL]
    supported_data_types = [DataType.SUPPLEMENTARY]

    def pull_data(self):
        startkey = None

        location_ids_to_delete = set(
            GoingElectricChargeLocation.objects.values_list("id", flat=True)
        )
        sites_created = 0

        while True:
            response = get_goingelectric_chargers(startkey=startkey)

            if response["status"] != "ok":
                raise RuntimeError("error getting data from GoingElectric API")

            for data in response["chargelocations"]:
                with transaction.atomic():
                    if data["network"]:
                        network, _ = GoingElectricNetwork.objects.get_or_create(
                            name=data["network"]
                        )
                    else:
                        network = None
                    location, created = (
                        GoingElectricChargeLocation.objects.update_or_create(
                            id=data["ge_id"],
                            defaults=dict(
                                name=data["name"],
                                coordinates=Point(
                                    data["coordinates"]["lng"],
                                    data["coordinates"]["lat"],
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
                                network=network,
                                url=data["url"],
                                fault_report=data["fault_report"],
                                verified=data["verified"],
                            ),
                        )
                    )

                    if created:
                        sites_created += 1

                    chargepoints = GoingElectricChargepoint.objects.filter(
                        chargelocation=location
                    ).order_by("type", "power", "count")
                    if chargepoints.count() != len(data["chargepoints"]) or any(
                        chargepoint.type != cp["type"]
                        or chargepoint.power != cp["power"]
                        or chargepoint.count != cp["count"]
                        for chargepoint, cp in zip(
                            chargepoints,
                            sorted(
                                data["chargepoints"],
                                key=lambda x: (x["type"], x["power"], x["count"]),
                            ),
                        )
                    ):
                        chargepoints.delete()
                        for chargepoint in data["chargepoints"]:
                            GoingElectricChargepoint.objects.create(
                                chargelocation=location,
                                type=chargepoint["type"],
                                power=chargepoint["power"],
                                count=chargepoint["count"],
                            )

                    location_ids_to_delete.discard(location.id)

            if "startkey" in response:
                startkey = response["startkey"]
                print(startkey)
            else:
                break

        # Delete all remaining sites that weren't in the input
        if location_ids_to_delete:
            GoingElectricChargeLocation.objects.filter(
                id__in=location_ids_to_delete
            ).delete()
            sites_deleted = len(location_ids_to_delete)
        else:
            sites_deleted = 0

        print(f"{sites_created} sites created, {sites_deleted} sites deleted")
