import os

import pytz
import requests

from evmap_backend.data_sources import DataType
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2SloveniaDataSource(BaseDatex2DataSource):
    id = "slovenia"
    license_attribution = "Slovenian Ministry of Infrastructure, CC-BY 4.0"
    license_attribution_link = (
        "https://www.gov.si/en/state-authorities/ministries/ministry-of-infrastructure/"
    )
    # https://nap.si/en/datasets_details?id=46963663-38dd-eb04-43a9-cca9bdc0e4ba

    def get_data(self) -> str:
        response = requests.get(
            "https://b2b.nap.si/data/b2b.prometej.energyInfrastructureTablePublication",
            auth=(
                os.environ["SLOVENIA_NAP_USERNAME"],
                os.environ["SLOVENIA_NAP_PASSWORD"],
            ),
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text


class Datex2SloveniaRealtimeDataSource(BaseDatex2DataSource):
    id = "slovenia_realtime"
    license_attribution = "Slovenian Ministry of Infrastructure, CC-BY 4.0"
    license_attribution_link = (
        "https://www.gov.si/en/state-authorities/ministries/ministry-of-infrastructure/"
    )
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "slovenia"
    default_timezone = pytz.timezone("Europe/Ljubljana")
    # https://nap.si/en/datasets_details?id=acc8a643-9dac-ecad-58da-0ce20f88f4bd

    def get_data(self) -> str:
        response = requests.get(
            "https://b2b.nap.si/data/b2b.prometej.energyInfrastructureStatusPublication",
            auth=(
                os.environ["SLOVENIA_NAP_USERNAME"],
                os.environ["SLOVENIA_NAP_PASSWORD"],
            ),
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
