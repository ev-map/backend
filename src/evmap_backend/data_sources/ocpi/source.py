import gzip
import json
import os
from abc import abstractmethod
from typing import Iterable, List

import requests

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.ocpi.parser import OcpiLocation, OcpiParser
from evmap_backend.sync import sync_chargers


def deduplicate_chargers(chargers: Iterable[OcpiLocation]) -> Iterable[OcpiLocation]:
    chargers_by_id = {}
    for charger in chargers:
        if (
            charger.id in chargers_by_id
            and chargers_by_id[charger.id].last_updated > charger.last_updated
        ):
            continue
        chargers_by_id[charger.id] = charger
    return chargers_by_id.values()


class BaseOcpiDataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]

    @abstractmethod
    def get_locations_data(self) -> Iterable[dict]:
        """Get the data from the data source"""
        pass

    def postprocess_locations(
        self, locations: Iterable[OcpiLocation]
    ) -> Iterable[OcpiLocation]:
        return locations

    def pull_data(self):
        root = self.get_locations_data()
        locations = OcpiParser().parse(root)
        locations = self.postprocess_locations(locations)
        sync_chargers(self.id, (location.convert(self.id) for location in locations))


class BaseEcoMovementUkOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://open-chargepoints.com/api/ocpi/cpo/2.2.1/locations"
    tariffs_url = "https://open-chargepoints.com/api/ocpi/cpo/2.2.1/tariffs"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]

    @property
    @abstractmethod
    def token(self) -> str:
        pass

    def get_locations_data(self):
        offset = 0
        limit = 1000
        while True:
            response = requests.get(
                self.locations_url,
                params={"limit": limit, "offset": offset},
                headers={"Authorization": f"Token {self.token}"},
            )
            result = json.loads(response.text)["data"]
            for item in result:
                yield item
            if len(result) < limit:
                break
            offset += limit


class NdwNetherlandsOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz"
    tariffs_url = "https://opendata.ndw.nu/charging_point_tariffs_ocpi.json.gz"

    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    id = "ndw_netherlands"

    def get_locations_data(self):
        response = requests.get(self.locations_url)
        unzipped = gzip.decompress(response.content).decode("utf-8")
        return json.loads(unzipped)

    def postprocess_locations(
        self, locations: Iterable[OcpiLocation]
    ) -> Iterable[OcpiLocation]:
        # dataset contains duplicate chargers with the same ID. These are actually the same location, but with outdated data
        return deduplicate_chargers(locations)


class BpPulseUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("BP_PULSE_UK_ECOMOVEMENT_TOKEN")
    id = "bp_pulse_uk"


class IonityUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("IONITY_UK_ECOMOVEMENT_TOKEN")
    id = "ionity_uk"


class BlinkUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("BLINK_UK_ECOMOVEMENT_TOKEN")
    id = "blink_uk"


class EsbUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("ESB_UK_ECOMOVEMENT_TOKEN")
    id = "esb_uk"


class BpPulseUkOcpiRealtimeDataSource(BaseOcpiDataSource):
    statuses_url = "https://open-chargepoints.com/api/statuses"

    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]


class ChargyUkOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://char.gy/open-ocpi/locations"
    tariffs_url = "https://char.gy/open-ocpi/tariffs/GB/CGY"

    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    id = "chargy_uk"

    def get_locations_data(self):
        return json.loads(requests.get(self.locations_url).text)["data"]


class MfgUkOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://opendata.motorfuelgroup.net/locations"
    tariffs_url = "https://opendata.motorfuelgroup.net/tariffs"

    supported_data_types = [DataType.STATIC, DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    id = "mfg_uk"

    def get_locations_data(self):
        return json.loads(requests.get(self.locations_url).text)["data"]
