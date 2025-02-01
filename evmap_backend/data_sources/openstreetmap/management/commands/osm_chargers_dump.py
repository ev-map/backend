import datetime

import requests
from django.contrib.gis.geos import Point
from django.core.management import BaseCommand

from evmap_backend.data_sources.openstreetmap.models import (OsmNode,
                                                             OsmUpdateState)

OVERPASS_INTERPRETER = "https://overpass-api.de/api/interpreter"
TIMEOUT_SECONDS = 900  # 15m


class Command(BaseCommand):
    help = "Connects to OpenStreetMap Overpass API to extract charger information"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        last_update = OsmUpdateState.get_solo().last_update
        print(f"last update: {last_update}")
        newer_query = (
            f'(newer:"{last_update.isoformat()}")' if last_update is not None else ""
        )

        now = datetime.datetime.now()
        response = requests.post(
            OVERPASS_INTERPRETER,
            timeout=TIMEOUT_SECONDS,
            data=f"[out:json][timeout:{TIMEOUT_SECONDS}]; node{newer_query}[amenity=charging_station]; out meta qt;",
            headers={"Content-Type": "text/plain"},
        ).json()
        print(f"received {len(response['elements'])} nodes")
        for el in response["elements"]:
            OsmNode(
                id=el["id"],
                location=Point(el["lon"], el["lat"]),
                timestamp=el["timestamp"],
                version=el["version"],
                user=el["user"],
                uid=el["uid"],
                tags=el["tags"],
            ).save()

        state = OsmUpdateState.get_solo()
        state.last_update = now
        state.save()
