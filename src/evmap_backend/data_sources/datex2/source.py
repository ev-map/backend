import os
from abc import abstractmethod
from urllib.parse import unquote_to_bytes

import requests
from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_certificates
from cryptography.x509.verification import PolicyBuilder, Store
from django.http import HttpRequest
from django.utils import timezone

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.settings import BASE_DIR
from evmap_backend.sync import sync_chargers, sync_statuses


class BaseDatex2DataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    parser = Datex2XmlParser()

    realtime_station_as_site = False
    """Workaround for wrong data where sites are represented as stations in the realtime data."""

    @abstractmethod
    def get_data(self) -> str:
        """Get the data from the data source"""
        pass

    @property
    def static_data_source(self) -> str:
        raise NotImplementedError()

    def pull_data(self):
        root = self.get_data()
        self._parse_data(root)

    def process_push(self, body: bytes):
        root = body.decode("utf-8")
        self._parse_data(root)

    def _parse_data(self, root: str):
        if self.supported_data_types == [DataType.STATIC]:
            sites_datex = self.parser.parse(root)
            sync_chargers(self.id, (site.convert(self.id) for site in sites_datex))
        elif self.supported_data_types == [DataType.DYNAMIC]:
            statuses_datex = self.parser.parse_status(
                root, station_as_site=self.realtime_station_as_site
            )
            sync_statuses(
                self.id,
                self.static_data_source,
                (s for status in statuses_datex for s in status.convert(self.id)),
            )
        else:
            raise NotImplementedError()


mobilithek_store = Store(
    load_pem_x509_certificates(
        open(BASE_DIR / "evmap_backend/certificates/mobilithek.pem", "rb").read()
    )
)


class BaseMobilithekDatex2DataSource(BaseDatex2DataSource):
    supported_update_methods = [UpdateMethod.PULL, UpdateMethod.HTTP_PUSH]
    ignore_encoding = False

    @property
    @abstractmethod
    def subscription_id(self):
        pass

    def get_data(self) -> str:
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": self.subscription_id,
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        if self.ignore_encoding:
            response.encoding = response.apparent_encoding
        return response.text

    def verify_push(self, request: HttpRequest):
        if "X-Forwarded-Client-Cert" not in request.headers:
            raise PermissionError("Client certificate missing")

        cert_header = request.headers["X-Forwarded-Client-Cert"]
        cert = load_pem_x509_certificate(unquote_to_bytes(cert_header))
        verifier = (
            PolicyBuilder()
            .store(mobilithek_store)
            .time(timezone.now())
            .build_client_verifier()
        )
        verifier.verify(cert, [])


class Datex2AustriaDataSource(BaseDatex2DataSource):
    id = "e-control_austria"

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


class Datex2AustriaRealtimeDataSource(BaseDatex2DataSource):
    id = "e-control_austria_realtime"

    def get_data(self) -> str:
        response = requests.get(
            "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-status-publication",
            headers={
                "Accept": "application/xml",
                "Apikey": os.environ["ECONTROL_API_KEY"],
                "Referer": "https://ev-map.app",
            },
        )
        return response.text


class Datex2MobilithekEcoMovementDatex2DataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ecomovement"
    subscription_id = os.environ.get("MOBILITHEK_ECOMOVEMENT_STATIC_SUBSCRIPTION_ID")
    ignore_encoding = True


class Datex2MobilithekEcoMovementRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ecomovement_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ECOMOVEMENT_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ecomovement"


class Datex2MobilithekEnbwDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enbw"
    subscription_id = os.environ.get("MOBILITHEK_ENBW_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()


class Datex2MobilithekEnbwRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enbw_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ENBW_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_enbw"
    parser = Datex2JsonParser()


class Datex2MobilithekLadenetzDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ladenetz"
    subscription_id = os.environ.get("MOBILITHEK_LADENETZ_STATIC_SUBSCRIPTION_ID")


class Datex2MobilithekLadenetzRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ladenetz_realtime"
    subscription_id = os.environ.get("MOBILITHEK_LADENETZ_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ladenetz"
    realtime_station_as_site = True


class Datex2MobilithekUlmDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ulm"
    subscription_id = os.environ.get("MOBILITHEK_ULM_STATIC_SUBSCRIPTION_ID")


class Datex2MobilithekUlmRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ulm_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ULM_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ulm"
    realtime_station_as_site = True


class Datex2MobilithekWirelaneDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_wirelane"
    subscription_id = os.environ.get("MOBILITHEK_WIRELANE_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()


class Datex2MobilithekWirelaneRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_wirelane_realtime"
    subscription_id = os.environ.get("MOBILITHEK_WIRELANE_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_wirelane"


class Datex2LuxembourgEcoMovementDataSource(BaseDatex2DataSource):
    id = "luxembourg_ecomovement"

    def get_data(self) -> str:
        response = requests.get(
            "https://api.eco-movement.com/api/nap/datexii/locations",
            params={
                "token": os.environ["ECOMOVEMENT_LUXEMBOURG_TOKEN"],
            },
        )
        response.encoding = response.apparent_encoding
        return response.text
