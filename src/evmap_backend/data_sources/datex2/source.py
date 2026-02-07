import os
from abc import abstractmethod
from typing import Optional
from urllib.parse import unquote_to_bytes

import pytz
import requests
from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_certificates
from cryptography.x509.verification import PolicyBuilder, Store
from django.http import HttpRequest
from django.utils import timezone
from django.utils.functional import classproperty

from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.settings import BASE_DIR
from evmap_backend.sync import sync_chargers, sync_statuses


class BaseDatex2DataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution_link: Optional[str] = None
    parser = Datex2XmlParser()
    default_timezone = None

    realtime_station_as_site = False
    """Workaround for wrong data where sites are represented as stations in the realtime data."""

    @abstractmethod
    def get_data(self) -> str:
        """Get the data from the data source"""
        pass

    @property
    def static_data_source(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    @classproperty
    def license_attribution(self) -> str:
        pass

    def pull_data(self):
        root = self.get_data()
        self._parse_data(root)

    def process_push(self, body: bytes):
        root = body.decode("utf-8")
        self._parse_data(root)

    def _parse_data(self, root: str):
        if self.supported_data_types == [DataType.STATIC]:
            sites_datex = self.parser.parse(root)
            sync_chargers(
                self.id,
                (
                    site.convert(
                        self.id, self.license_attribution, self.license_attribution_link
                    )
                    for site in sites_datex
                ),
            )
        elif self.supported_data_types == [DataType.DYNAMIC]:
            statuses_datex = self.parser.parse_status(
                root,
                station_as_site=self.realtime_station_as_site,
                default_timezone=self.default_timezone,
            )
            sync_statuses(
                self.id,
                self.static_data_source,
                (
                    s
                    for status in statuses_datex
                    for s in status.convert(
                        self.id, self.license_attribution, self.license_attribution_link
                    )
                ),
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
        response.raise_for_status()
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
    license_attribution = "E-Control"
    license_attribution_link = "http://www.e-control.at/"
    # https://admin.ladestellen.at/#/api/registrieren

    def get_data(self) -> str:
        response = requests.get(
            "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-table-publication",
            headers={
                "Accept": "application/xml",
                "Apikey": os.environ["ECONTROL_API_KEY"],
                "Referer": "https://ev-map.app",
            },
        )
        response.raise_for_status()
        return response.text


class Datex2AustriaRealtimeDataSource(BaseDatex2DataSource):
    id = "e-control_austria_realtime"
    supported_data_types = [DataType.DYNAMIC]
    license_attribution = "E-Control"
    license_attribution_link = "http://www.e-control.at/"
    # https://admin.ladestellen.at/#/api/registrieren

    def get_data(self) -> str:
        response = requests.get(
            "https://api.e-control.at/charge/1.0/datex2/v3.5/energy-infrastructure-status-publication",
            headers={
                "Accept": "application/xml",
                "Apikey": os.environ["ECONTROL_API_KEY"],
                "Referer": "https://ev-map.app",
            },
        )
        response.raise_for_status()
        return response.text


class Datex2MobilithekEcoMovementDatex2DataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ecomovement"
    subscription_id = os.environ.get("MOBILITHEK_ECOMOVEMENT_STATIC_SUBSCRIPTION_ID")
    ignore_encoding = True
    license_attribution = "Eco-Movement BV, CC-BY 4.0"
    # https://mobilithek.info/offers/855030183015186432


class Datex2MobilithekEcoMovementRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ecomovement_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ECOMOVEMENT_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    parser = Datex2JsonParser()
    static_data_source = "mobilithek_ecomovement"
    license_attribution = "Eco-Movement BV, CC-BY 4.0"
    # https://mobilithek.info/offers/904394594561454080


class Datex2MobilithekEnbwDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enbw"
    subscription_id = os.environ.get("MOBILITHEK_ENBW_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "EnBW AG, CC-BY 4.0"
    # https://mobilithek.info/offers/907574882292453376


class Datex2MobilithekEnbwRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enbw_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ENBW_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_enbw"
    parser = Datex2JsonParser()
    license_attribution = "EnBW AG, CC-BY 4.0"
    # https://mobilithek.info/offers/907575401287241728


class Datex2MobilithekLadenetzDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ladenetz"
    subscription_id = os.environ.get("MOBILITHEK_LADENETZ_STATIC_SUBSCRIPTION_ID")
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    ignore_encoding = True
    # https://mobilithek.info/offers/902547569133924352


class Datex2MobilithekLadenetzRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ladenetz_realtime"
    subscription_id = os.environ.get("MOBILITHEK_LADENETZ_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ladenetz"
    realtime_station_as_site = True
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    # https://mobilithek.info/offers/903240716507836416


class Datex2MobilithekUlmDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ulm"
    subscription_id = os.environ.get("MOBILITHEK_ULM_STATIC_SUBSCRIPTION_ID")
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    # https://mobilithek.info/offers/854410608351543296


class Datex2MobilithekUlmRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ulm_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ULM_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ulm"
    realtime_station_as_site = True
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    # https://mobilithek.info/offers/854416606814023680


class Datex2MobilithekWirelaneDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_wirelane"
    subscription_id = os.environ.get("MOBILITHEK_WIRELANE_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Wirelane GmbH, CC-0"
    # https://mobilithek.info/offers/869246425829892096


class Datex2MobilithekWirelaneRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_wirelane_realtime"
    subscription_id = os.environ.get("MOBILITHEK_WIRELANE_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_wirelane"
    license_attribution = "Wirelane GmbH, CC-0"
    # https://mobilithek.info/offers/876587237907525632


class BaseEcoMovementNapDatex2DataSource(BaseDatex2DataSource):
    license_attribution = "Eco-Movement BV"
    # https://developers.eco-movement.com/v5/docs/eco-movement-data-api-datex

    @abstractmethod
    @classproperty
    def token(self) -> str:
        pass

    def get_data(self) -> str:
        response = requests.get(
            "https://api.eco-movement.com/api/nap/datexii/locations",
            params={
                "token": self.token,
            },
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text


class Datex2LuxembourgEcoMovementDataSource(BaseEcoMovementNapDatex2DataSource):
    id = "luxembourg_ecomovement"
    token = os.environ.get("ECOMOVEMENT_LUXEMBOURG_TOKEN")
    # https://data.public.lu/en/datasets/bornes-de-chargement-publiques-pour-voitures-electriques-du-plusieurs-operateurs-1/


class Datex2DenmarkEcoMovementDataSource(BaseEcoMovementNapDatex2DataSource):
    id = "denmark_ecomovement"
    token = os.environ.get("ECOMOVEMENT_DENMARK_TOKEN")
    # https://du-portal-ui.dataudveksler.app.vd.dk/data/950/overview


class Datex2BelgiumEcoMovementDataSource(BaseEcoMovementNapDatex2DataSource):
    id = "belgium_ecomovement"
    token = os.environ.get("ECOMOVEMENT_BELGIUM_TOKEN")
    # https://transportdata.be/de/dataset/afir-static-dataset-selected-cpos


class Datex2SloveniaDataSource(BaseDatex2DataSource):
    id = "slovenia"
    license_attribution = "Slovenian Ministry of Infrastructure, CC-BY 4.0"
    license_attribution_link = (
        "https://www.gov.si/en/state-authorities/ministries/ministry-of-infrastructure/"
    )
    # https://nap.si/en/datasets_details?id=46963663-38dd-eb04-43a9-cca9bdc0e4ba

    def get_data(self) -> str:
        response = requests.get(
            "https://b2b.nap.si/data/b2b.prometej.energyInfrastructureTablePublication",
            auth=(
                os.environ["SLOVENIA_NAP_USERNAME"],
                os.environ["SLOVENIA_NAP_PASSWORD"],
            ),
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text


class Datex2SloveniaRealtimeDataSource(BaseDatex2DataSource):
    id = "slovenia_realtime"
    license_attribution = "Slovenian Ministry of Infrastructure, CC-BY 4.0"
    license_attribution_link = (
        "https://www.gov.si/en/state-authorities/ministries/ministry-of-infrastructure/"
    )
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "slovenia"
    default_timezone = pytz.timezone("Europe/Ljubljana")
    # https://nap.si/en/datasets_details?id=acc8a643-9dac-ecad-58da-0ce20f88f4bd

    def get_data(self) -> str:
        response = requests.get(
            "https://b2b.nap.si/data/b2b.prometej.energyInfrastructureStatusPublication",
            auth=(
                os.environ["SLOVENIA_NAP_USERNAME"],
                os.environ["SLOVENIA_NAP_PASSWORD"],
            ),
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
