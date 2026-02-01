from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from django.http import HttpRequest
from django.utils.functional import classproperty


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
    """Data can be retrieved by calling pull_data from a cron job"""

    HTTP_PUSH = 2
    """
    Data source an call our server at /push/{data_source_id} to push new data.
    verify_push and process_push have to be implemented.
    """

    STREAMING = 3
    """A background service runs continuously (e.g., with an MQTT connection) to receive streaming updates with the
    stream_data method."""

    OCPI_PUSH = 4
    """Data source pushes data using the OCPI protocol."""


class DataSource(ABC):
    @classproperty
    @abstractmethod
    def id(self) -> str:
        pass

    @classproperty
    @abstractmethod
    def supported_data_types(self) -> List[DataType]:
        pass

    @classproperty
    @abstractmethod
    def supported_update_methods(self) -> List[UpdateMethod]:
        pass

    def pull_data(self):
        raise NotImplementedError()

    def verify_push(self, request: HttpRequest):
        raise NotImplementedError()

    def process_push(self, body: bytes):
        raise NotImplementedError()

    def stream_data(self):
        raise NotImplementedError()

    def setup(self):
        """Optional setup steps for this data source to be run during server startup.

        This has to be idempotent, i.e., check whether setup has already been done.
        """
        pass
