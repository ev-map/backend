import requests

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.opendata_swiss.parser import (
    parse_oicp_data,
    parse_oicp_status,
)
from evmap_backend.data_sources.sync import sync_chargers, sync_statuses

DATA_URL = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"
STATUS_URL = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/status/oicp/ch.bfe.ladestellen-elektromobilitaet.json"


class OpendataSwissDataSource(DataSource):
    id = "opendata_swiss"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "opendata.swiss"
    license_attribution_link = (
        "https://opendata.swiss/de/dataset/ladestationen-fuer-elektroautos"
    )

    def pull_data(self):
        response = requests.get(DATA_URL)
        response.raise_for_status()
        data = response.json()

        sites = parse_oicp_data(
            data,
            self.id,
            self.license_attribution,
            self.license_attribution_link,
        )
        sync_chargers(self.id, sites)


class OpendataSwissRealtimeDataSource(DataSource):
    id = "opendata_swiss_realtime"
    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "opendata.swiss"
    license_attribution_link = (
        "https://opendata.swiss/de/dataset/ladestationen-fuer-elektroautos"
    )

    def pull_data(self):
        response = requests.get(STATUS_URL)
        response.raise_for_status()
        status_data = response.json()

        statuses = parse_oicp_status(
            status_data,
            self.id,
            self.license_attribution,
            self.license_attribution_link,
        )
        sync_statuses(self.id, "opendata_swiss", statuses)
