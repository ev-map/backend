from abc import abstractmethod

import requests
from django.utils.functional import classproperty

from evmap_backend.data_sources import DataType
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.source import BaseDatex2DataSource


class BaseSpiriiDatex2DataSource(BaseDatex2DataSource):
    parser = Datex2JsonParser()

    @abstractmethod
    @classproperty
    def customer_id(self) -> int:
        pass

    def get_data(self) -> str:
        url = (
            f"https://api.spirii.com/v2/afir/energy-infrastructure-statuses?customerIds={self.customer_id}"
            if DataType.DYNAMIC in self.supported_data_types
            else f"https://api.spirii.com/v2/afir/energy-infrastructure-tables?customerIds={self.customer_id}"
        )
        response = requests.get(url)
        response.raise_for_status()
        return response.text


# class Datex2AudiChargingHubDataSource(BaseSpiriiDatex2DataSource):
#     id = "audi_charging_hub"
#     license_attribution = "Audi AG"
#     customer_id = 128650
#     # https://mobilithek.info/offers/980858103788171264
#
#
# class Datex2AudiChargingHubRealtimeDataSource(BaseSpiriiDatex2DataSource):
#     id = "audi_charging_hub_realtime"
#     license_attribution = "Audi AG"
#     supported_data_types = [DataType.DYNAMIC]
#     customer_id = 128650
#     static_data_source = "audi_charging_hub"
#     # https://mobilithek.info/offers/980860692042825728
