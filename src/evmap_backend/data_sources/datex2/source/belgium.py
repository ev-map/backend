import os

import requests

from evmap_backend.data_sources import DataType
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2BelgiumIndigoDataSource(BaseDatex2DataSource):
    id = "belgium_indigo"
    license_attribution = "Group INDIGO, ODbL 1.0"
    # https://transportdata.be/en/dataset/indigo-open-data-evcharging

    def get_data(self) -> str:
        response = requests.get(
            "https://transportdata.be/dataset/27f1357d-71ee-48cb-84a1-96f3f4f034b8/resource/d4bc8ddd-c80f-4330-98e5-d86e5b2147c3/download/indigo-data-evcharging-static-datexii.xml",
        )
        response.raise_for_status()
        return response.text


class Datex2BelgiumEnergyVisionDataSource(BaseDatex2DataSource):
    id = "belgium_energyvision"
    license_attribution = "EnergyVision"
    api_key = os.environ.get("ENERGYVISION_BELGIUM_API_KEY")
    # https://transportdata.be/en/dataset/energyvision-public-charging-network-afir-datex

    def get_data(self) -> str:
        response = requests.get(
            "https://datex.cpo.energyvision.be/datex/energy-infrastructure-table",
            headers={
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        response.raise_for_status()
        return response.text


class Datex2BelgiumEnergyVisionRealtimeDataSource(BaseDatex2DataSource):
    id = "belgium_energyvision_realtime"
    license_attribution = "EnergyVision"
    api_key = os.environ.get("ENERGYVISION_BELGIUM_API_KEY")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "belgium_energyvision"
    # https://transportdata.be/en/dataset/energyvision-public-charging-network-afir-datex

    def get_data(self) -> str:
        response = requests.get(
            "https://datex.cpo.energyvision.be/datex/energy-infrastructure-status",
            headers={
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        response.raise_for_status()
        return response.text
