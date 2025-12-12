from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from django.http import HttpRequest


class DataType(Enum):
    STATIC = 1
    """
    Basic static charging station data (e.g., location, operator, number and type of chargers).
    Stored using the evmap_backend.chargers models.
    """

    DYNAMIC = 2
    """Real-time status"""

    PRICING = 3
    """Pricing information"""

    SUPPLEMENTARY = 4
    """
    Supplementary, typically community-contributed data like photos, descriptions, comments. Stored using separate, own
    models per data source.
    """


class UpdateMethod(Enum):
    PULL = 1
    """Data can be retrieved by calling load_data from a cron job"""

    HTTP_PUSH = 2
    """
    Data source an call our server at /push/{data_source_id} to push new data.
    verify_push and process_push have to be implemented.
    """

    BACKGROUND_SERVICE = 3
    """A background service needs to run continuously (e.g., with an MQTT connection) to receive updates"""


class DataSource(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def supported_data_types(self) -> List[DataType]:
        pass

    @property
    @abstractmethod
    def supported_update_methods(self) -> List[UpdateMethod]:
        pass

    @abstractmethod
    def load_data(self):
        pass

    def verify_push(self, request: HttpRequest):
        raise NotImplementedError()

    def process_push(self, body: bytes):
        raise NotImplementedError()
