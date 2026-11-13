import datetime
import os
from abc import abstractmethod
from urllib.parse import unquote_to_bytes

import requests
from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_certificates
from cryptography.x509.verification import PolicyBuilder, Store
from django.http import HttpRequest
from django.utils import timezone

from evmap_backend.data_sources import DataType, UpdateMethod
from evmap_backend.data_sources.datex2.parser.json import Datex2JsonParser
from evmap_backend.data_sources.datex2.parser.xml import Datex2XmlParser
from evmap_backend.data_sources.datex2.source import (
    BaseDatex2DataSource,
    NotModifiedError,
)
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.settings import BASE_DIR

with open(BASE_DIR / "evmap_backend/certificates/mobilithek.pem", "rb") as file:
    mobilithek_store = Store(load_pem_x509_certificates(file.read()))


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
    # https://mobilithek.info/offers/1056537528692871168


class Datex2MobilithekM8MitRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_m8mit_realtime"
    subscription_id = os.environ.get("MOBILITHEK_M8MIT_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_m8mit"
    license_attribution = "msu solutions GmbH"
    # https://mobilithek.info/offers/1056536080202764288


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


class Datex2MobilithekRoadDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_road"
    subscription_id = os.environ.get("MOBILITHEK_ROAD_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Road B.V."
    # https://mobilithek.info/offers/1021366453630017536


class Datex2MobilithekRoadRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_road_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ROAD_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_road"
    license_attribution = "Road B.V."
    # https://mobilithek.info/offers/1021364001002217472


class Datex2MobilithekEweDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ewe"
    subscription_id = os.environ.get("MOBILITHEK_EWE_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "EWE, CC-0"
    # https://mobilithek.info/offers/1024264572575293440


class Datex2MobilithekEweRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_ewe_realtime"
    subscription_id = os.environ.get("MOBILITHEK_EWE_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_ewe"
    license_attribution = "EWE, CC-0"
    # https://mobilithek.info/offers/1006184570533171200


class Datex2MobilithekInergiaDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_inergia"
    subscription_id = os.environ.get("MOBILITHEK_INERGIA_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "INERGIA GmbH, CC-0"
    # https://mobilithek.info/offers/1043944773714128896


class Datex2MobilithekInergiaRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_inergia_realtime"
    subscription_id = os.environ.get("MOBILITHEK_INERGIA_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_inergia"
    license_attribution = "INERGIA GmbH, CC-0"
    # https://mobilithek.info/offers/1043947032435105792


class Datex2MobilithekEnerandoDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enerando"
    subscription_id = os.environ.get("MOBILITHEK_ENERANDO_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "ENERANDO Technologies GmbH"
    # https://mobilithek.info/offers/1037036344672452608


class Datex2MobilithekEnerandoRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_enerando_realtime"
    subscription_id = os.environ.get("MOBILITHEK_ENERANDO_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_enerando"
    license_attribution = "ENERANDO Technologies GmbH"
    # https://mobilithek.info/offers/1037038702374617088


class Datex2MobilithekVirtaDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_virta"
    subscription_id = os.environ.get("MOBILITHEK_VIRTA_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "Virta International GmbH, CC-0"
    # https://mobilithek.info/offers/1042468553977937920


class Datex2MobilithekVirtaRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_virta_realtime"
    subscription_id = os.environ.get("MOBILITHEK_VIRTA_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_virta"
    license_attribution = "Virta International GmbH, CC-0"
    # https://mobilithek.info/offers/1042472664437800960


class Datex2MobilithekInnoceptDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_innocept"
    subscription_id = os.environ.get("MOBILITHEK_INNOCEPT_STATIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    license_attribution = "innocept mobility GmbH"
    # https://mobilithek.info/offers/1019404392733597696


class Datex2MobilithekInnoceptRealtimeDataSource(BaseMobilithekDatex2DataSource):
    id = "mobilithek_innocept_realtime"
    subscription_id = os.environ.get("MOBILITHEK_INNOCEPT_DYNAMIC_SUBSCRIPTION_ID")
    parser = Datex2JsonParser()
    supported_data_types = [DataType.DYNAMIC]
    static_data_source = "mobilithek_innocept"
    license_attribution = "innocept mobility GmbH"
    # https://mobilithek.info/offers/1026876702612758528
