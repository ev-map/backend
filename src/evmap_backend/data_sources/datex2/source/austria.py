import os

import requests

from evmap_backend.data_sources import DataType
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2AustriaDataSource(BaseDatex2DataSource):
    id = "e-control_austria"
    license_attribution = "E-Control"
    license_attribution_link = "http://www.e-control.at/"
    # https://admin.ladestellen.at/#/api/registrieren

    def get_data(self) -> str:
        response = requests.get(
            "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-table-publication",
            headers={
                "Accept": "application/xml",
                "Apikey": os.environ["ECONTROL_API_KEY"],
                "Referer": "https://ev-map.app",
            },
        )
        response.raise_for_status()
        return response.text


class Datex2AustriaRealtimeDataSource(BaseDatex2DataSource):
    id = "e-control_austria_realtime"
    supported_data_types = [DataType.DYNAMIC]
    license_attribution = "E-Control"
    license_attribution_link = "http://www.e-control.at/"
    static_data_source = "e-control_austria"
    # https://admin.ladestellen.at/#/api/registrieren

    def get_data(self) -> str:
        response = requests.get(
            "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-status-publication",
            headers={
                "Accept": "application/xml",
                "Apikey": os.environ["ECONTROL_API_KEY"],
                "Referer": "https://ev-map.app",
            },
        )
        response.raise_for_status()
        return response.text
