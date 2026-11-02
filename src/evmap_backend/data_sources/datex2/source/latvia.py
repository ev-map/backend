import os
from abc import abstractmethod

import requests
from django.utils.functional import classproperty

from evmap_backend.data_sources import DataType
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class BaseDatex2LatviaDataSource(BaseDatex2DataSource):
    @abstractmethod
    @classproperty
    def api_key(self) -> str:
        pass

    def get_data(self) -> str:
        response = requests.get(
            "https://www.transportdata.gov.lv/api/v1/metadata/file/info",
            headers={"x-api-key": self.api_key},
        ).json()
        file_id = response["files"][0]["file_id"]
        response = requests.post(
            "https://www.transportdata.gov.lv/api/v1/get/file/download-file",
            headers={"x-api-key": self.api_key},
            json={"file_id": file_id, "format": "xml"},
        )
        response.raise_for_status()
        return response.text


class Datex2LatviaEcoMovementDataSource(BaseDatex2LatviaDataSource):
    id = "latvia_ecomovement"
    license_attribution = "Eco-Movement B.V."
    api_key = os.environ.get("LATVIA_ECOMOVEMENT_API_KEY")
    # https://www.transportdata.gov.lv/en/card/d8e419c3-1585-4666-9067-85712befd2c4


class Datex2LatviaEcoMovementRealtimeDataSource(BaseDatex2LatviaDataSource):
    id = "latvia_ecomovement_realtime"
    license_attribution = "Eco-Movement B.V."
    api_key = os.environ.get("LATVIA_ECOMOVEMENT_REALTIME_API_KEY")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "latvia_ecomovement"
    # https://www.transportdata.gov.lv/en/card/a377a160-baa1-4b67-b4e8-6612cd289e22
