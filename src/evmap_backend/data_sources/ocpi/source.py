import gzip
import json
from typing import List

import requests

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.ocpi.parser import OcpiParser
from evmap_backend.sync import sync_chargers

LOCATIONS_URL = "https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz"
TARIFFS_URL = "https://opendata.ndw.nu/charging_point_tariffs_ocpi.json.gz"
SOURCE = "ndw_netherlands"


def deduplicate_chargers(chargers):
    chargers_by_id = {}
    for charger in chargers:
        if (
            charger.id in chargers_by_id
            and chargers_by_id[charger.id].last_updated > charger.last_updated
        ):
            continue
        chargers_by_id[charger.id] = charger
    return chargers_by_id.values()


def get_ndw_data():
    response = requests.get(LOCATIONS_URL)
    unzipped = gzip.decompress(response.content).decode("utf-8")
    return json.loads(unzipped)


class OcpiDataSource(DataSource):
    @property
    def id(self) -> str:
        return "ndw_netherlands"

    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.STATIC]

    @property
    def supported_update_methods(self) -> List[UpdateMethod]:
        return [UpdateMethod.PULL]

    def pull_data(self):
        root = get_ndw_data()
        ndw_chargers = OcpiParser().parse(root)

        # dataset contains duplicate chargers with the same ID. These are actually the same location, but with outdated data
        ndw_chargers = deduplicate_chargers(ndw_chargers)

        sync_chargers(SOURCE, (location.convert(SOURCE) for location in ndw_chargers))
