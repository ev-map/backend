import datetime
import logging
import os
from abc import abstractmethod
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
from evmap_backend.data_sources.models import OAuthToken, UpdateState
from evmap_backend.data_sources.sync import sync_chargers, sync_statuses
from evmap_backend.settings import BASE_DIR

logger = logging.getLogger(__name__)


class BaseDatex2DataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution_link: str | None = None
    parser = Datex2XmlParser()
    default_timezone = None
    default_country = None

    @abstractmethod
    def get_data(self) -> str:
        """Get the data from the data source"""

    @property
    def static_data_source(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    @classproperty
    def license_attribution(self) -> str:
        pass

    def pull_data(self):
        try:
            root = self.get_data()
            self._parse_data(root)
        except NotModifiedError:
            logger.info("Not modified")

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
                        self.id,
                        self.license_attribution,
                        self.license_attribution_link,
                        self.default_country,
                    )
                    for site in sites_datex
                ),
            )
        elif self.supported_data_types == [DataType.DYNAMIC]:
            statuses_datex = self.parser.parse_status(
                root,
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


with open(BASE_DIR / "evmap_backend/certificates/mobilithek.pem", "rb") as file:
    mobilithek_store = Store(load_pem_x509_certificates(file.read()))


class NotModifiedError(Exception):
    pass


class BaseMobilithekDatex2DataSource(BaseDatex2DataSource):
    supported_update_methods = [UpdateMethod.PULL, UpdateMethod.HTTP_PUSH]
    ignore_encoding = False

    @property
    @abstractmethod
    def subscription_id(self):
        pass

    def get_data(self) -> str:
        try:
            update_state = UpdateState.objects.get(data_source=self.id)
            last_update = update_state.last_update.astimezone(datetime.UTC)
        except UpdateState.DoesNotExist:
            last_update = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)
        response = requests.get(
            "https://mobilithek.info:8443/mobilithek/api/v1.0/subscription",
            params={
                "subscriptionID": self.subscription_id,
            },
            headers={
                "If-Modified-Since": last_update.strftime("%a, %d %b %Y %H:%M:%S GMT")
            },
            cert=os.environ["MOBILITHEK_CERTIFICATE"],
        )
        response.raise_for_status()
        if response.status_code == 304:
            raise NotModifiedError()
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
    static_data_source = "e-control_austria"
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
    parser = Datex2JsonParser()
    license_attribution = "Eco-Movement BV, CC-BY 4.0"
    # https://mobilithek.info/offers/954064102947180544


class Datex2MobilithekEcoMovementRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ecomovement_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ECOMOVEMENT_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    parser = Datex2JsonParser()
    static_data_source = "mobilithek_ecomovement"
    license_attribution = "Eco-Movement BV, CC-BY 4.0"
    # https://mobilithek.info/offers/955166494396665856


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
    parser = Datex2XmlParser(realtime_station_as_site=True)
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    # https://mobilithek.info/offers/903240716507836416


class Datex2MobilithekLadebusinessDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ladebusiness"
    subscription_id = os.environ.get("MOBILITHEK_LADEBUSINESS_STATIC_SUBSCRIPTION_ID")
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    ignore_encoding = True
    # https://mobilithek.info/offers/903241622921695232


class Datex2MobilithekLadebusinessRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ladebusiness_realtime"
    subscription_id = os.environ.get("MOBILITHEK_LADEBUSINESS_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ladebusiness"
    parser = Datex2XmlParser(realtime_station_as_site=True)
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    # https://mobilithek.info/offers/903321397006716928


class Datex2MobilithekEClearingDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eclearing"
    subscription_id = os.environ.get("MOBILITHEK_ECLEARING_STATIC_SUBSCRIPTION_ID")
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    parser = Datex2JsonParser()
    # https://mobilithek.info/offers/996825300704600064


class Datex2MobilithekEClearingRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eclearing_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ECLEARING_DYNAMIC_SUBSCRIPTION_ID")
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_eclearing"
    parser = Datex2JsonParser()
    license_attribution = "Smartlab Innovationsgesellschaft mbH, CC-0"
    # https://mobilithek.info/offers/996823601386508288


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
    parser = Datex2XmlParser(realtime_station_as_site=True)
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


class Datex2MobilithekTeslaDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_tesla"
    subscription_id = os.environ.get("MOBILITHEK_TESLA_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Tesla Germany GmbH, CC-0"
    # https://mobilithek.info/offers/953828817873125376


class Datex2MobilithekTeslaRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_tesla_realtime"
    subscription_id = os.environ.get("MOBILITHEK_TESLA_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_tesla"
    license_attribution = "Tesla Germany GmbH, CC-0"
    # https://mobilithek.info/offers/953843379766972416


class Datex2MobilithekSmatricsDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_smatrics"
    subscription_id = os.environ.get("MOBILITHEK_SMATRICS_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "SMATRICS GmbH & Co KG, CC-0"
    # https://mobilithek.info/offers/961317352759001088


class Datex2MobilithekSmatricsRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_smatrics_realtime"
    subscription_id = os.environ.get("MOBILITHEK_SMATRICS_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_smatrics"
    license_attribution = "SMATRICS GmbH & Co KG, CC-0"
    # https://mobilithek.info/offers/961319990963605504


class Datex2MobilithekEroundDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eround"
    subscription_id = os.environ.get("MOBILITHEK_EROUND_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Hamburger Energienetze GmbH, CC-0"
    # https://mobilithek.info/offers/961625658278940672


class Datex2MobilithekEroundRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eround_realtime"
    subscription_id = os.environ.get("MOBILITHEK_EROUND_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_eround"
    license_attribution = "Hamburger Energienetze GmbH, CC-0"
    # https://mobilithek.info/offers/961629419076456448


class Datex2MobilithekMontaDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_monta"
    subscription_id = os.environ.get("MOBILITHEK_MONTA_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Monta Aps"
    # https://mobilithek.info/offers/963836072152719360


class Datex2MobilithekMontaRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_monta_realtime"
    subscription_id = os.environ.get("MOBILITHEK_MONTA_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_monta"
    license_attribution = "Monta ApS"
    # https://mobilithek.info/offers/963870983660167168


class Datex2MobilithekGridAndCoDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_gridandco"
    subscription_id = os.environ.get("MOBILITHEK_GRIDANDCO_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Grid & Co. GmbH"
    # https://mobilithek.info/offers/984104561811357696


class Datex2MobilithekGridAndCoRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_gridandco_realtime"
    subscription_id = os.environ.get("MOBILITHEK_GRIDANDCO_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_gridandco"
    license_attribution = "Grid & Co. GmbH"
    # https://mobilithek.info/offers/984103903968534528


class Datex2MobilithekEnioDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enio"
    subscription_id = os.environ.get("MOBILITHEK_ENIO_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "ENIO GmbH"
    # https://mobilithek.info/offers/963766220171735040


class Datex2MobilithekEnioRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enio_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ENIO_DYNAMIC_SUBSCRIPTION_ID")
    static_data_source = "mobilithek_enio"
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    license_attribution = "ENIO GmbH"
    # https://mobilithek.info/offers/968541134128902144


class Datex2MobilithekPumpDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_pump"
    subscription_id = os.environ.get("MOBILITHEK_PUMP_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "800 Volt Technologies GmbH, CC-0"
    # https://mobilithek.info/offers/969322788846231552


class Datex2MobilithekM8MitDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_m8mit"
    subscription_id = os.environ.get("MOBILITHEK_M8MIT_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "msu solutions GmbH"
    # https://mobilithek.info/offers/970305056590979072


class Datex2MobilithekM8MitRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_m8mit_realtime"
    subscription_id = os.environ.get("MOBILITHEK_M8MIT_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_m8mit"
    license_attribution = "msu solutions GmbH"
    # https://mobilithek.info/offers/970388804493828096


class Datex2MobilithekEluMobilityDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_elumobility"
    subscription_id = os.environ.get("MOBILITHEK_ELUMOBILITY_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "ELU Mobility"
    # https://mobilithek.info/offers/936298491949047808


class Datex2MobilithekEluMobilityRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_elumobility_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ELUMOBILITY_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_elumobility"
    license_attribution = "ELU Mobility"
    # https://mobilithek.info/offers/971513500454850560


class Datex2MobilithekQwelloDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_qwello"
    subscription_id = os.environ.get("MOBILITHEK_QWELLO_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Qwello Deutschland GmbH, CC-0"
    # https://mobilithek.info/offers/972963216296222720


class Datex2MobilithekQwelloRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_qwello_realtime"
    subscription_id = os.environ.get("MOBILITHEK_QWELLO_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_qwello"
    license_attribution = "Qwello Deutschland GmbH, CC-0"
    # https://mobilithek.info/offers/972966368902897664


class Datex2MobilithekEonDriveDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eon_drive"
    subscription_id = os.environ.get("MOBILITHEK_EON_DRIVE_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Аmpeco Ltd., CC-0"
    # https://mobilithek.info/offers/972837891969273856


class Datex2MobilithekEonDriveRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eon_drive_realtime"
    subscription_id = os.environ.get("MOBILITHEK_EON_DRIVE_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_eon_drive"
    license_attribution = "Аmpeco Ltd., CC-0"
    # https://mobilithek.info/offers/972842599324557312


class Datex2MobilithekChargecloudDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_chargecloud"
    subscription_id = os.environ.get("MOBILITHEK_CHARGECLOUD_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "chargecloud GmbH, CC-0"
    # https://mobilithek.info/offers/978597062404620288


class Datex2MobilithekChargecloudRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_chargecloud_realtime"
    subscription_id = os.environ.get("MOBILITHEK_CHARGECLOUD_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_chargecloud"
    license_attribution = "chargecloud GmbH, CC-0"
    # https://mobilithek.info/offers/978598831184601088


class Datex2MobilithekEulektroDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eulektro"
    subscription_id = os.environ.get("MOBILITHEK_EULEKTRO_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser(station_as_chargepoint=True)
    license_attribution = "Eulektro GmbH"
    # https://mobilithek.info/offers/973938793916375040


class Datex2MobilithekEulektroRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_eulektro_realtime"
    subscription_id = os.environ.get("MOBILITHEK_EULEKTRO_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_eulektro"
    license_attribution = "Eulektro GmbH"
    # https://mobilithek.info/offers/974006122901856256


class Datex2MobilithekVaylensDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_vaylens"
    subscription_id = os.environ.get("MOBILITHEK_VAYLENS_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "vaylens GmbH"
    # https://mobilithek.info/offers/979363267193040896


class Datex2MobilithekVaylensRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_vaylens_realtime"
    subscription_id = os.environ.get("MOBILITHEK_VAYLENS_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_vaylens"
    license_attribution = "vaylens GmbH"
    # https://mobilithek.info/offers/979364650281549824


class Datex2MobilithekGlsMobilityDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_glsmobility"
    subscription_id = os.environ.get("MOBILITHEK_GLSMOBILITY_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "GLS Mobility"
    # https://mobilithek.info/offers/980559859451379712


class Datex2MobilithekGlsMobilityRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_glsmobility_realtime"
    subscription_id = os.environ.get("MOBILITHEK_GLSMOBILITY_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_glsmobility"
    license_attribution = "GLS Mobility"
    # https://mobilithek.info/offers/980563757096464384


class Datex2MobilithekLichtBlickDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_lichtblick"
    subscription_id = os.environ.get("MOBILITHEK_LICHTBLICK_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "LichtBlick eMobility GmbH"
    # https://mobilithek.info/offers/962721207430316032


class Datex2MobilithekLichtBlickRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_lichtblick_realtime"
    subscription_id = os.environ.get("MOBILITHEK_LICHTBLICK_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_lichtblick"
    license_attribution = "LichtBlick eMobility GmbH"
    # https://mobilithek.info/offers/962731482363617280


class Datex2MobilithekEwPricingDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ew_pricing"
    subscription_id = os.environ.get("MOBILITHEK_EW_PRICING_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "EW Pricing GmbH"
    # https://mobilithek.info/offers/989311807176560640


class Datex2MobilithekEwPricingRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ew_pricing_realtime"
    subscription_id = os.environ.get("MOBILITHEK_EW_PRICING_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ew_pricing"
    license_attribution = "EW Pricing GmbH"
    # https://mobilithek.info/offers/989311073915731968


class Datex2MobilithekGpJouleDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_gp_joule"
    subscription_id = os.environ.get("MOBILITHEK_GP_JOULE_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "GP JOULE Connect GmbH, CC-0"
    # https://mobilithek.info/offers/997111469996658688


class Datex2MobilithekGpJouleRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_gp_joule_realtime"
    subscription_id = os.environ.get("MOBILITHEK_GP_JOULE_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_gp_joule"
    license_attribution = "GP JOULE Connect GmbH, CC-0"
    # https://mobilithek.info/offers/997190851637440512


class Datex2MobilithekTaubertConsultingDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_taubert_consulting"
    subscription_id = os.environ.get(
        "MOBILITHEK_TAUBERT_CONSULTING_STATIC_SUBSCRIPTION_ID"
    )
    parser = Datex2JsonParser()
    license_attribution = "Taubert Consulting GmbH, CC-0"
    # https://mobilithek.info/offers/1000749522967314432


class Datex2MobilithekTaubertConsultingRealtimeDataSource(
    BaseMobilithekDatex2DataSource
):
    id = "mobilithek_taubert_consulting_realtime"
    subscription_id = os.environ.get(
        "MOBILITHEK_TAUBERT_CONSULTING_DYNAMIC_SUBSCRIPTION_ID"
    )
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_taubert_consulting"
    license_attribution = "Taubert Consulting GmbH, CC-0"
    # https://mobilithek.info/offers/1000746576770711552


class Datex2MobilithekVolkswagenGroupChargingDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_vw_group_charging"
    subscription_id = os.environ.get(
        "MOBILITHEK_VW_GROUP_CHARGING_STATIC_SUBSCRIPTION_ID"
    )
    parser = Datex2JsonParser()
    license_attribution = "Volkswagen Group Charging, CC-0"
    # https://mobilithek.info/offers/983008874583728128


class Datex2MobilithekVolkswagenGroupChargingRealtimeDataSource(
    BaseMobilithekDatex2DataSource
):
    id = "mobilithek_vw_group_charging_realtime"
    subscription_id = os.environ.get(
        "MOBILITHEK_VW_GROUP_CHARGING_DYNAMIC_SUBSCRIPTION_ID"
    )
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_vw_group_charging"
    license_attribution = "Volkswagen Group Charging, CC-0"
    # https://mobilithek.info/offers/983006934617260032


class Datex2MobilithekFlaviaDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_flavia"
    subscription_id = os.environ.get("MOBILITHEK_FLAVIA_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Flavia IT-Management GmbH"
    # https://mobilithek.info/offers/1004450433724211200


class Datex2MobilithekFlaviaRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_flavia_realtime"
    subscription_id = os.environ.get("MOBILITHEK_FLAVIA_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_flavia"
    license_attribution = "Flavia IT-Management GmbH"
    # https://mobilithek.info/offers/1004756865530970112


class Datex2MobilithekAudiChargingHubDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_audi_charging_hub"
    subscription_id = os.environ.get(
        "MOBILITHEK_AUDI_CHARGING_HUB_STATIC_SUBSCRIPTION_ID"
    )
    parser = Datex2JsonParser()
    license_attribution = "Audi AG"
    # https://mobilithek.info/offers/998571342932365312


class Datex2MobilithekAudiChargingHubRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_audi_charging_hub_realtime"
    subscription_id = os.environ.get(
        "MOBILITHEK_AUDI_CHARGING_HUB_DYNAMIC_SUBSCRIPTION_ID"
    )
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_audi_charging_hub"
    license_attribution = "Audi AG"
    # https://mobilithek.info/offers/998567365272563712


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


class Datex2FinlandDataSource(BaseDatex2DataSource):
    id = "fintraffic"
    parser = Datex2JsonParser(station_as_chargepoint=True)
    license_attribution = "Fintraffic / digitraffic.fi, CC-BY 4.0"
    license_attribution_link = "https://www.digitraffic.fi/en/terms-of-service/"
    # https://www.digitraffic.fi/en/road-traffic/afir/

    def get_data(self) -> str:
        response = requests.get(
            "https://afir.digitraffic.fi/api/charging-network/v1/locations/datex2-3.6",
        )
        response.raise_for_status()
        return response.text


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


class Datex2SpainDataSource(BaseDatex2DataSource):
    id = "spain"
    license_attribution = "Dirección General de Tráfico, CC-BY 4.0"
    license_attribution_link = (
        "https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos"
    )
    default_country = "ES"
    # https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos

    def get_data(self) -> str:
        response = requests.get(
            "https://infocar.dgt.es/datex2/v3/miterd/EnergyInfrastructureTablePublication/electrolineras.xml",
        )
        response.raise_for_status()
        return response.text


class Datex2DenmarkOkDataSource(BaseDatex2DataSource):
    id = "denmark_ok"
    license_attribution = "OK A.M.B.A."
    token = os.environ.get("OK_DENMARK_TOKEN")
    # https://du-portal-ui.dataudveksler.app.vd.dk/data/1096/overview

    def get_data(self) -> str:
        response = requests.get(
            f"https://ocpi-emobility.okcloud.dk/datex/locations?token={self.token}",
        )
        response.raise_for_status()
        return response.text


class BaseMontaPublicDatex2DataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    parser = Datex2JsonParser()
    license_attribution = "Monta ApS"
    # https://docs.public-api.monta.com/reference/get-afir-charge-points

    token_id = "monta_public_api"
    api_url = "https://public-api.monta.com/api/v1/afir/charge-points"
    token_url = "https://public-api.monta.com/api/v1/auth/token"
    refresh_url = "https://public-api.monta.com/api/v1/auth/refresh"

    def _get_monta_token(self):
        token = OAuthToken(id=self.id)
        response = requests.post(
            self.token_url,
            json={
                "clientId": os.environ.get("MONTA_PUBLIC_API_CLIENT_ID"),
                "clientSecret": os.environ.get("MONTA_PUBLIC_API_CLIENT_SECRET"),
            },
        ).json()
        token.access_token = response["accessToken"]
        token.refresh_token = response["refreshToken"]
        token.access_token_expires = datetime.datetime.fromisoformat(
            response["accessTokenExpirationDate"]
        )
        token.refresh_token_expires = datetime.datetime.fromisoformat(
            response["refreshTokenExpirationDate"]
        )
        token.save()
        return token

    def _refresh_monta_token(self, token):
        token = OAuthToken.objects.get(id=self.token_id)
        response = requests.post(
            self.refresh_url, json={"refreshToken": token.refresh_token}
        ).json()

        token.access_token = response["accessToken"]
        token.refresh_token = response["refreshToken"]
        token.access_token_expires = datetime.datetime.fromisoformat(
            response["accessTokenExpirationDate"]
        )
        token.refresh_token_expires = datetime.datetime.fromisoformat(
            response["refreshTokenExpirationDate"]
        )
        token.save()
        return token

    def _get_token(self):
        now = timezone.now()
        try:
            token = OAuthToken.objects.get(id=self.token_id)
        except OAuthToken.DoesNotExist:
            token = self._get_monta_token()

        if token.refresh_token_expires <= now:
            token = self._refresh_monta_token(token)
        elif token.access_token_expires <= now:
            token = self._get_monta_token()
        return token

    @abstractmethod
    @classproperty
    def country(self) -> str:
        pass

    def get_page(self, page: int, access_token: str, per_page: int = 1000) -> dict:
        response = requests.get(
            self.api_url,
            params={
                "country": self.country,
                "page": page,
                "perPage": per_page,
            },
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
        )
        response.raise_for_status()
        return response.json()

    def parse_all_pages(self):
        token = self._get_token()
        page = 1
        while True:
            root = self.get_page(page, token.access_token)
            yield from self.parser.parse(root)

            if root["meta"]["total"] <= root["meta"]["page"] * root["meta"]["perPage"]:
                break
            page += 1

    def pull_data(self):
        sites_datex = self.parse_all_pages()
        sync_chargers(
            self.id,
            (
                site.convert(
                    self.id,
                    self.license_attribution,
                    None,
                    self.country,
                )
                for site in sites_datex
            ),
        )


class Datex2DenmarkMontaDataSource(BaseMontaPublicDatex2DataSource):
    id = "denmark_monta"
    country = "DK"


class Datex2BelgiumMontaDataSource(BaseMontaPublicDatex2DataSource):
    id = "belgium_monta"
    country = "BE"
