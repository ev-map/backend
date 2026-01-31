import gzip
import json
import os
from abc import abstractmethod
from typing import Iterable, Optional

import requests
from django.utils.functional import classproperty

from evmap_backend import settings
from evmap_backend.data_sources import DataSource, DataType, UpdateMethod
from evmap_backend.data_sources.ocpi import SUPPORTED_OCPI_VERSIONS
from evmap_backend.data_sources.ocpi.model import (
    OcpiBusinessDetails,
    OcpiCredentials,
    OcpiCredentialsRole,
)
from evmap_backend.data_sources.ocpi.models import OcpiConnection, generate_token
from evmap_backend.data_sources.ocpi.parser import OcpiLocation, OcpiParser
from evmap_backend.data_sources.ocpi.utils import (
    ocpi_get,
    ocpi_get_paginated,
    ocpi_post,
)
from evmap_backend.sync import sync_chargers, sync_statuses


def deduplicate_chargers(chargers: Iterable[OcpiLocation]) -> Iterable[OcpiLocation]:
    chargers_by_id = {}
    for charger in chargers:
        if (
            charger.id in chargers_by_id
            and chargers_by_id[charger.id].last_updated > charger.last_updated
        ):
            continue
        chargers_by_id[charger.id] = charger
    return chargers_by_id.values()


class BaseOcpiDataSource(DataSource):
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution_link: Optional[str] = None

    @abstractmethod
    @classproperty
    def license_attribution(self) -> str:
        pass

    @abstractmethod
    def get_locations_data(self) -> Iterable[dict]:
        """Get the data from the data source"""
        pass

    def postprocess_locations(
        self, locations: Iterable[OcpiLocation]
    ) -> Iterable[OcpiLocation]:
        return locations

    def pull_data(self):
        root = self.get_locations_data()
        locations = OcpiParser().parse_locations(root)
        locations = self.postprocess_locations(locations)
        if DataType.DYNAMIC in self.supported_data_types:
            locations = list(locations)

        sync_chargers(
            self.id,
            (
                location.convert(
                    self.id, self.license_attribution, self.license_attribution_link
                )
                for location in locations
            ),
        )
        if DataType.DYNAMIC in self.supported_data_types:
            sync_statuses(
                self.id,
                self.id,
                (
                    s
                    for location in locations
                    for s in location.convert_status(
                        self.id, self.license_attribution, self.license_attribution_link
                    )
                ),
            )


class BaseOcpiRealtimeDataSource(DataSource):
    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution_link: Optional[str] = None

    @abstractmethod
    @classproperty
    def license_attribution(self) -> str:
        pass

    @abstractmethod
    def get_statuses_data(self) -> Iterable[dict]:
        """Get the data from the data source"""
        pass

    @property
    @abstractmethod
    def locations_data_source(self) -> str:
        pass

    def pull_data(self):
        root = self.get_statuses_data()
        locations = OcpiParser().parse_locations(root, status_only=True)
        sync_statuses(
            self.id,
            self.locations_data_source,
            (
                s
                for location in locations
                for s in location.convert_status(
                    self.id, self.license_attribution, self.license_attribution_link
                )
            ),
        )


class BaseOcpiConnectionDataSource(DataSource):
    """
    Base class for OCPI data sources that uses an OCPI connection and receives data updates via push
    """

    supported_data_types = [DataType.STATIC, DataType.DYNAMIC, DataType.PRICING]
    supported_update_methods = [UpdateMethod.PULL, UpdateMethod.OCPI_PUSH]
    license_attribution_link: Optional[str] = None
    is_credentials_sender: bool = False
    role = "NSP"
    country_code = os.environ.get("OCPI_COUNTRY_CODE")
    party_id = os.environ.get("OCPI_PARTY_ID")
    business_name = os.environ.get("OCPI_BUSINESS_NAME")

    def __init__(self):
        if self.is_credentials_sender:
            OcpiConnection.objects.get_or_create(
                data_source=self.id, defaults={"token_a": ""}
            )
        else:
            OcpiConnection.objects.get_or_create(data_source=self.id)

    @abstractmethod
    @classproperty
    def license_attribution(self) -> str:
        pass

    def postprocess_locations(
        self, locations: Iterable[OcpiLocation]
    ) -> Iterable[OcpiLocation]:
        return locations

    def pull_data(self):
        conn = OcpiConnection.objects.get(data_source=self.id)
        token = conn.token_c if self.is_credentials_sender else conn.token_b

        if not token:
            if self.is_credentials_sender:
                self._send_credentials(conn)
            else:
                raise ValueError(f"OCPI connection has not completed handshake yet")
        if not conn.locations_url and not conn.tariffs_url:
            self._fetch_endpoints(conn)

        root = ocpi_get_paginated(conn.locations_url, token)
        locations = list(OcpiParser().parse_locations(root))
        locations = self.postprocess_locations(locations)
        sync_chargers(
            self.id,
            (
                location.convert(
                    self.id, self.license_attribution, self.license_attribution_link
                )
                for location in locations
            ),
        )
        sync_statuses(
            self.id,
            self.id,
            (
                s
                for location in locations
                for s in location.convert_status(
                    self.id, self.license_attribution, self.license_attribution_link
                )
            ),
        )

    def _fetch_endpoints(self, conn: OcpiConnection):
        versions = ocpi_get(conn.url, conn.token_b)
        version = next(v for v in versions if v["version"] == conn.version)
        version_detail = ocpi_get(version["url"], conn.token_b)

        for endpoint in version_detail["endpoints"]:
            if endpoint["identifier"] == "locations" and (
                "role" not in endpoint or endpoint["role"] == "SENDER"
            ):
                conn.locations_url = endpoint["url"]
            if endpoint["identifier"] == "tariffs" and (
                "role" not in endpoint or endpoint["role"] == "SENDER"
            ):
                conn.tariffs_url = endpoint["url"]

        conn.save()

    def _send_credentials(self, conn: OcpiConnection):
        if not conn.token_a:
            raise ValueError(f"OCPI connection has no Token A set")
        if not conn.url:
            raise ValueError(f"OCPI connection has no URL set")

        versions = ocpi_get(conn.url, conn.token_a)

        supported_ocpi_versions = [
            v for v in versions if v["version"] in SUPPORTED_OCPI_VERSIONS
        ]
        best_version = max(supported_ocpi_versions, key=lambda v: v["version"])
        conn.version = best_version["version"]

        version_detail = ocpi_get(best_version["url"], conn.token_a)
        credentials_url = None
        for endpoint in version_detail["endpoints"]:
            if endpoint["identifier"] == "locations" and (
                "role" not in endpoint or endpoint["role"] == "SENDER"
            ):
                conn.locations_url = endpoint["url"]
            if endpoint["identifier"] == "tariffs" and (
                "role" not in endpoint or endpoint["role"] == "SENDER"
            ):
                conn.tariffs_url = endpoint["url"]
            if endpoint["identifier"] == "credentials" and (
                "role" not in endpoint or endpoint["role"] == "RECEIVER"
            ):
                credentials_url = endpoint["url"]

        if not credentials_url:
            raise ValueError("No credentials endpoint found in OCPI version detail")

        conn.token_b = generate_token()
        conn.save()

        response = ocpi_post(
            credentials_url,
            conn.token_a,
            OcpiCredentials(
                token=conn.token_b,
                url=settings.SITE_URL + "/ocpi/versions",
                roles=[
                    OcpiCredentialsRole(
                        role=self.role,
                        country_code=self.country_code,
                        party_id=self.party_id,
                        business_details=OcpiBusinessDetails(
                            name=self.business_name,
                        ),
                    )
                ],
            ),
        )
        conn.token_c = response["token"]
        conn.save()


class BaseEcoMovementUkOcpiDataSource(BaseOcpiDataSource):
    """
    Base class for static data from Eco-Movement's PCPR API (based on OCPI) for the UK
    https://developers.eco-movement.com/docs/eco-movement-pcpr-api-user-guide
    """

    locations_url = "https://open-chargepoints.com/api/ocpi/cpo/2.2.1/locations"
    tariffs_url = "https://open-chargepoints.com/api/ocpi/cpo/2.2.1/tariffs"
    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "Eco-Movement BV"

    @property
    @abstractmethod
    def token(self) -> str:
        pass

    def get_locations_data(self):
        offset = 0
        limit = 1000
        while True:
            response = requests.get(
                self.locations_url,
                params={"limit": limit, "offset": offset},
                headers={"Authorization": f"Token {self.token}"},
            )
            response.raise_for_status()
            result = json.loads(response.text)["data"]
            for item in result:
                yield item
            if len(result) < limit:
                break
            offset += limit


class BaseEcoMovementUkOcpiRealtimeDataSource(BaseOcpiRealtimeDataSource):
    """
    Base class for realtime status data from Eco-Movement's PCPR API (based on OCPI) for the UK
    https://developers.eco-movement.com/docs/eco-movement-pcpr-api-user-guide
    """

    statuses_url = "https://open-chargepoints.com/api/statuses"
    supported_data_types = [DataType.DYNAMIC]
    supported_update_methods = [UpdateMethod.PULL]
    license_attribution = "Eco-Movement BV"

    @property
    @abstractmethod
    def token(self) -> str:
        pass

    def get_statuses_data(self) -> Iterable[dict]:
        response = requests.get(
            self.statuses_url,
            headers={"Authorization": f"Token {self.token}"},
        )
        response.raise_for_status()
        return json.loads(response.text)["data"]


class NdwNetherlandsOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz"
    tariffs_url = "https://opendata.ndw.nu/charging_point_tariffs_ocpi.json.gz"
    license_attribution = "Nationaal Dataportaal Wegverkeer"
    # https://docs.ndw.nu/en/data-uitwisseling/interface-beschrijvingen/dafne-api

    supported_data_types = [DataType.STATIC, DataType.DYNAMIC]
    id = "ndw_netherlands"

    def get_locations_data(self):
        response = requests.get(self.locations_url)
        unzipped = gzip.decompress(response.content).decode("utf-8")
        return json.loads(unzipped)

    def postprocess_locations(
        self, locations: Iterable[OcpiLocation]
    ) -> Iterable[OcpiLocation]:
        # dataset contains duplicate chargers with the same ID. These are actually the same location, but with outdated data
        return deduplicate_chargers(locations)


class BpPulseUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("BP_PULSE_UK_ECOMOVEMENT_TOKEN")
    id = "bp_pulse_uk"
    # https://www.bppulse.com/en-gb/help-and-support/public-ev-charging/public-charge-point-regulations


class BpPulseUkOcpiRealtimeDataSource(BaseEcoMovementUkOcpiRealtimeDataSource):
    token = os.environ.get("BP_PULSE_UK_ECOMOVEMENT_TOKEN")
    id = "bp_pulse_uk_realtime"
    locations_data_source = "bp_pulse_uk"
    # https://www.bppulse.com/en-gb/help-and-support/public-ev-charging/public-charge-point-regulations


class IonityUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("IONITY_UK_ECOMOVEMENT_TOKEN")
    id = "ionity_uk"
    # https://www.ionity.eu/open-data-request


class IonityUkOcpiRealtimeDataSource(BaseEcoMovementUkOcpiRealtimeDataSource):
    token = os.environ.get("IONITY_UK_ECOMOVEMENT_TOKEN")
    id = "ionity_uk_realtime"
    locations_data_source = "ionity_uk"
    # https://www.ionity.eu/open-data-request


class BlinkUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("BLINK_UK_ECOMOVEMENT_TOKEN")
    id = "blink_uk"
    # https://blinkcharging.com/en-gb/getintouch/blink-open-data-request


class BlinkUkOcpiRealtimeDataSource(BaseEcoMovementUkOcpiRealtimeDataSource):
    token = os.environ.get("BLINK_UK_ECOMOVEMENT_TOKEN")
    id = "blink_uk_realtime"
    locations_data_source = "blink_uk"
    # https://blinkcharging.com/en-gb/getintouch/blink-open-data-request


class EsbUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("ESB_UK_ECOMOVEMENT_TOKEN")
    id = "esb_uk"
    # https://www.esbenergy.co.uk/ev/charge-points -> PCPR Data Request


class EsbUkOcpiRealtimeDataSource(BaseEcoMovementUkOcpiRealtimeDataSource):
    token = os.environ.get("ESB_UK_ECOMOVEMENT_TOKEN")
    id = "esb_uk_realtime"
    locations_data_source = "esb_uk"
    # https://www.esbenergy.co.uk/ev/charge-points -> PCPR Data Request


class ShellRechargeUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    # Includes both Shell Recharge and Ubitricity chargers in the UK
    token = os.environ.get("SHELLRECHARGE_UK_ECOMOVEMENT_TOKEN")
    id = "shellrecharge_uk"
    # https://www.shell.co.uk/electric-vehicle-charging/public-charge-point-regulations.html


class ShellRechargeUkOcpiRealtimeDataSource(BaseEcoMovementUkOcpiRealtimeDataSource):
    token = os.environ.get("SHELLRECHARGE_UK_ECOMOVEMENT_TOKEN")
    id = "shellrecharge_uk_realtime"
    locations_data_source = "shellrecharge_uk"
    # https://www.shell.co.uk/electric-vehicle-charging/public-charge-point-regulations.html


class CommunityByShellRechargeUkOcpiDataSource(BaseEcoMovementUkOcpiDataSource):
    token = os.environ.get("SHELLRECHARGE_COMMUNITY_UK_ECOMOVEMENT_TOKEN")
    id = "shellrecharge_community_uk"
    # https://www.shell.co.uk/electric-vehicle-charging/public-charge-point-regulations.html


class CommunityByShellRechargeUkOcpiRealtimeDataSource(
    BaseEcoMovementUkOcpiRealtimeDataSource
):
    token = os.environ.get("SHELLRECHARGE_COMMUNITY_UK_ECOMOVEMENT_TOKEN")
    id = "shellrecharge_community_uk_realtime"
    locations_data_source = "shellrecharge_community_uk"
    # https://www.shell.co.uk/electric-vehicle-charging/public-charge-point-regulations.html


class ChargyUkOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://char.gy/open-ocpi/locations"
    tariffs_url = "https://char.gy/open-ocpi/tariffs/GB/CGY"
    license_attribution = "char.gy Ltd"
    # https://help.char.gy/support/solutions/articles/77000576948-public-charge-point-regulations-2023

    supported_data_types = [DataType.STATIC]
    supported_update_methods = [UpdateMethod.PULL]
    id = "chargy_uk"

    def get_locations_data(self):
        return json.loads(requests.get(self.locations_url).text)["data"]


class MfgUkOcpiDataSource(BaseOcpiDataSource):
    locations_url = "https://opendata.motorfuelgroup.net/locations"
    tariffs_url = "https://opendata.motorfuelgroup.net/tariffs"

    supported_data_types = [DataType.STATIC, DataType.DYNAMIC]
    id = "mfg_uk"
    license_attribution = "Motor Fuel Limited"
    # https://www.motorfuelgroup.com/ev-power/ -> Open data

    def get_locations_data(self):
        response = requests.get(self.locations_url)
        response.raise_for_status()
        return json.loads(response.text)["data"]


class LatviaOcpiDataSource(BaseOcpiDataSource):
    id = "latvia"
    supported_data_types = [DataType.STATIC, DataType.DYNAMIC]
    locations_url = "https://ev.vialietuva.lt/ocpi/2.2.1/locations"
    tariffs_url = "https://ev.vialietuva.lt/ocpi/2.2.1/tariffs"
    license_attribution = "Via Lietuva, CC-BY 4.0"
    # https://ev.lakd.lt/en/open_source

    def get_locations_data(self):
        response = requests.get(self.locations_url)
        response.raise_for_status()
        return json.loads(response.text)["data"]


class TeslaUkOcpiDataSource(BaseOcpiConnectionDataSource):
    id = "tesla_uk"
    license_attribution = "Tesla, Inc."
    # https://developer.tesla.com/docs/charging/roaming


class InstavoltUkOcpiDataSource(BaseOcpiConnectionDataSource):
    id = "instavolt_uk"
    license_attribution = "Instavolt Ltd., Open Government Licence"
    is_credentials_sender = True
    party_id = os.environ.get("INSTAVOLT_UK_OCPI_PARTY_ID")
    # https://instavolt.co.uk/public-charge-point-regulation-data/
