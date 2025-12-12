import datetime
import os
from typing import List, Optional

import requests

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.nobil.parser import parse_nobil_chargers
from evmap_backend.sync import sync_chargers


class NobilDataSource(DataSource):
    @property
    def id(self) -> str:
        return "nobil"

    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.STATIC]

    @property
    def supported_update_methods(self) -> List[UpdateMethod]:
        return [UpdateMethod.PULL]

    def get_nobil_dump(self, fromdate: Optional[datetime.datetime] = None):
        response = requests.get(
            "https://nobil.no/api/server/datadump.php",
            params={
                "apikey": os.environ["NOBIL_API_KEY"],
                "format": "json",
                "file": "false",
                "fromdate": fromdate.date() if fromdate is not None else None,
            },
        )
        return response.json()

    def load_data(self):
        update_state = UpdateState.objects.filter(data_source=self.id).first()
        last_update = update_state.last_update if update_state else None
        print(f"last update: {last_update}")

        dump = self.get_nobil_dump(last_update)
        sites_nobil = parse_nobil_chargers(dump)
        sync_chargers(
            self.id,
            (site.convert(self.id) for site in sites_nobil if site.ocpi_id is not None),
        )


class NobilRealtimeDataSource(DataSource):
    @property
    def id(self) -> str:
        return "nobil_realtime"

    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.DYNAMIC]

    @property
    def supported_update_methods(self) -> List[UpdateMethod]:
        return [UpdateMethod.BACKGROUND_SERVICE]
