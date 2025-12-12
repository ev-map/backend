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
    def supports_push(self) -> bool:
        pass

    @abstractmethod
    def load_data(self):
        pass

    def verify_push(self, request: HttpRequest):
        raise NotImplementedError()

    def process_push(self, body: bytes):
        raise NotImplementedError()
