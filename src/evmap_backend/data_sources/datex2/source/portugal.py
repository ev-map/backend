import requests

from evmap_backend.data_sources import DataType
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class Datex2PortugalDataSource(BaseDatex2DataSource):
    id = "portugal"
    license_attribution = "Mobi-E"
    # https://nap-portugal.imt-ip.pt/nap/multimodalsupplydetail/148

    def get_data(self) -> str:
        response = requests.get(
            "https://ev-nap.mobie.pt/integration/nap/evChargingInfra",
        )
        response.raise_for_status()
        return response.text


class Datex2PortugalRealtimeDataSource(BaseDatex2DataSource):
    id = "portugal_realtime"
    license_attribution = "Mobi-E"
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "portugal"
    # https://nap-portugal.imt-ip.pt/nap/multimodalsupplydetail/149

    def get_data(self) -> str:
        response = requests.get(
            "https://ev-nap.mobie.pt/integration/nap/evActualStatus",
        )
        response.raise_for_status()
        return response.text
