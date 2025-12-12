import os
from abc import abstractmethod
from typing import List

import requests

from evmap_backend.data_sources import DataSource, DataType
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.sync import sync_chargers


class BaseDatex2DataSource(DataSource):
    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.STATIC]

    @property
    def supports_push(self) -> bool:
        return True

    @abstractmethod
    def get_data(self) -> str:
        """Get the data from the data source"""
        pass

    def get_parser(self):
        """Get the appropriate parser for this data source. Override for non-XML sources."""
        return Datex2XmlParser()

    def load_data(self):
        root = self.get_data()
        self._parse_data(root)

    def process_push(self, body: bytes):
        root = body.decode("utf-8")
        self._parse_data(root)

    def _parse_data(self, root: str):
        sites_datex = self.get_parser().parse(root)
        sync_chargers(self.id, (site.convert(self.id) for site in sites_datex))


class Datex2AustriaDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "e-control_austria"

    def get_data(self) -> str:
        response = requests.get(
            "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-table-publication",
            headers={
                "Accept": "application/xml",
                "Apikey": os.environ["ECONTROL_API_KEY"],
                "Referer": "https://ev-map.app",
            },
        )
        return response.text


class Datex2MobilithekEcoMovementDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "mobilithek_ecomovement"

    def get_data(self) -> str:
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": os.environ[
                    "MOBILITHEK_ECOMOVEMENT_STATIC_SUBSCRIPTION_ID"
                ],
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        response.encoding = response.apparent_encoding
        return response.text


class Datex2MobilithekEnbwDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "mobilithek_enbw"

    def get_data(self) -> str:
        """Get the JSON data from the data source"""
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": os.environ["MOBILITHEK_ENBW_STATIC_SUBSCRIPTION_ID"],
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        return response.text

    def get_parser(self):
        return Datex2JsonParser()


class Datex2MobilithekLadenetzDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "mobilithek_ladenetz"

    def get_data(self) -> str:
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": os.environ[
                    "MOBILITHEK_LADENETZ_STATIC_SUBSCRIPTION_ID"
                ],
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        response.encoding = response.apparent_encoding
        return response.text


class Datex2MobilithekUlmDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "mobilithek_ulm"

    def get_data(self) -> str:
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": os.environ["MOBILITHEK_ULM_STATIC_SUBSCRIPTION_ID"],
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        response.encoding = response.apparent_encoding
        return response.text


class Datex2MobilithekWirelaneDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "mobilithek_wirelane"

    def get_data(self) -> str:
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": os.environ[
                    "MOBILITHEK_WIRELANE_STATIC_SUBSCRIPTION_ID"
                ],
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        return response.text

    def get_parser(self):
        return Datex2JsonParser()


class Datex2LuxembourgEcoMovementDataSource(BaseDatex2DataSource):
    @property
    def id(self) -> str:
        return "luxembourg_ecomovement"

    def get_data(self) -> str:
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": os.environ[
                    "MOBILITHEK_LUXEMBOURG_ECOMOVEMENT_STATIC_SUBSCRIPTION_ID"
                ],
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        response.encoding = response.apparent_encoding
        return response.text
