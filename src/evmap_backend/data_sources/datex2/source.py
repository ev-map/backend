import os
from abc import abstractmethod
from datetime import datetime
from typing import List
from urllib.parse import unquote_to_bytes

import requests
from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_certificates
from cryptography.x509.verification import PolicyBuilder, Store
from django.http import HttpRequest

from evmap_backend.data_sources import DataSource, DataType
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.settings import BASE_DIR
from evmap_backend.sync import sync_chargers


class BaseDatex2DataSource(DataSource):
    @property
    def supported_data_types(self) -> List[DataType]:
        return [DataType.STATIC]

    @property
    def supports_push(self) -> bool:
        return False

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


mobilithek_store = Store(
    load_pem_x509_certificates(
        open(BASE_DIR / "evmap_backend/certificates/mobilithek.pem", "rb").read()
    )
)


class BaseMobilithekDatex2DataSource(BaseDatex2DataSource):
    @property
    def supports_push(self) -> bool:
        return True

    def verify_push(self, request: HttpRequest):
        if "X-Forwarded-Client-Cert" not in request.headers:
            raise PermissionError("Client certificate missing")

        cert_header = request.headers["X-Forwarded-Client-Cert"]
        cert = load_pem_x509_certificate(unquote_to_bytes(cert_header))
        verifier = (
            PolicyBuilder()
            .store(mobilithek_store)
            .time(datetime.now())
            .build_client_verifier()
        )
        verifier.verify(cert, [])


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


class Datex2MobilithekEcoMovementDatex2DataSource(BaseMobilithekDatex2DataSource):
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


class Datex2MobilithekEnbwDataSource(BaseMobilithekDatex2DataSource):
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


class Datex2MobilithekLadenetzDataSource(BaseMobilithekDatex2DataSource):
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


class Datex2MobilithekUlmDataSource(BaseMobilithekDatex2DataSource):
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


class Datex2MobilithekWirelaneDataSource(BaseMobilithekDatex2DataSource):
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
