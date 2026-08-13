import datetime
import enum
import logging
from collections.abc import Iterable
from math import sqrt

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from ninja import Schema
from pytz import timezone

from evmap_backend import settings
from evmap_backend.chargers.fields import normalize_evseid, validate_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources.sync import (
    ChargepointItem,
    ChargingSiteItem,
    RealtimeStatusItem,
)
from evmap_backend.helpers.database import none_to_blank
from evmap_backend.realtime.models import CurrentStatus

# OCPI spec: https://evroaming.org/wp-content/uploads/2025/02/OCPI-2.3.0.pdf

logger = logging.getLogger(__name__)


class OcpiResponse[DataT](Schema):
    data: DataT
    status_code: int
    status_message: str
    timestamp: datetime.datetime


class OcpiVersion(Schema):
    version: str
    url: str


class OcpiEndpoint(Schema):
    identifier: str
    role: str
    url: str


class OcpiVersionDetail(Schema):
    version: str
    endpoints: list[OcpiEndpoint]


class OcpiImage(Schema):
    url: str
    thumbnail: str = None
    category: str
    type: str
    width: int = None
    height: int = None


class OcpiBusinessDetails(Schema):
    name: str
    website: str | None = None
    logo: OcpiImage | None = None


class OcpiCredentialsRole(Schema):
    role: str
    party_id: str
    country_code: str
    business_details: OcpiBusinessDetails


class OcpiCredentials22(Schema):
    token: str
    url: str
    hub_party_id: str | None = None
    roles: list[OcpiCredentialsRole]


class OcpiCredentials21(Schema):
    token: str
    url: str
    business_details: OcpiBusinessDetails
    party_id: str
    country_code: str


def build_ocpi_credentials(
    ocpi_version: str,
    token: str,
    role: str,
    party_id: str,
    country_code: str,
    business_name: str,
) -> OcpiCredentials22 | OcpiCredentials21:
    url = settings.SITE_URL + "/ocpi/versions"
    if ocpi_version >= "2.2":
        return OcpiCredentials22(
            token=token,
            url=url,
            roles=[
                OcpiCredentialsRole(
                    role=role,
                    party_id=party_id,
                    country_code=country_code,
                    business_details=OcpiBusinessDetails(name=business_name),
                )
            ],
        )
    else:
        return OcpiCredentials21(
            token=token,
            url=url,
            party_id=party_id,
            country_code=country_code,
            business_details=OcpiBusinessDetails(name=business_name),
        )


class OcpiConnector(Schema):
    class ConnectorType(enum.StrEnum):
        CHADEMO = "CHADEMO"
        CHAOJI = "CHAOJI"  # The ChaoJi connector. The new generation charging connector, harmonized between CHAdeMO and GB/T. DC
        DOMESTIC_A = "DOMESTIC_A"
        DOMESTIC_B = "DOMESTIC_B"
        DOMESTIC_C = "DOMESTIC_C"
        DOMESTIC_D = "DOMESTIC_D"
        DOMESTIC_E = "DOMESTIC_E"
        DOMESTIC_F = "DOMESTIC_F"
        DOMESTIC_G = "DOMESTIC_G"
        DOMESTIC_H = "DOMESTIC_H"
        DOMESTIC_I = "DOMESTIC_I"
        DOMESTIC_J = "DOMESTIC_J"
        DOMESTIC_K = "DOMESTIC_K"
        DOMESTIC_L = "DOMESTIC_L"
        DOMESTIC_M = "DOMESTIC_M"
        DOMESTIC_N = "DOMESTIC_N"
        DOMESTIC_O = "DOMESTIC_O"
        GBT_AC = "GBT_AC"
        GBT_DC = "GBT_DC"
        IEC_60309_2_SINGLE_16 = "IEC_60309_2_single_16"  # CEE blue 16A
        IEC_60309_2_THREE_16 = "IEC_60309_2_three_16"  # CEE red 16A
        IEC_60309_2_THREE_32 = "IEC_60309_2_three_32"  # CEE red 32A
        IEC_60309_2_THREE_64 = "IEC_60309_2_three_64"  # CEE red 63A
        IEC_62196_T1 = "IEC_62196_T1"  # Type 1
        IEC_62196_T1_COMBO = "IEC_62196_T1_COMBO"  # CCS Type 1
        IEC_62196_T2 = "IEC_62196_T2"  # Type 2
        IEC_62196_T2_COMBO = "IEC_62196_T2_COMBO"  # CCS Type 2
        IEC_62196_T3A = "IEC_62196_T3A"  # Type 3A
        IEC_62196_T3C = "IEC_62196_T3C"  # Type 3C
        MCS = (
            "MCS"  # The MegaWatt Charging System (MCS) connector as developed by CharIN
        )
        NEMA_5_20 = "NEMA_5_20"
        NEMA_6_30 = "NEMA_6_30"
        NEMA_6_50 = "NEMA_6_50"
        NEMA_10_30 = "NEMA_10_30"
        NEMA_10_50 = "NEMA_10_50"
        NEMA_14_30 = "NEMA_14_30"
        NEMA_14_50 = "NEMA_14_50"
        PANTOGRAPH_BOTTOM_UP = "PANTOGRAPH_BOTTOM_UP"  # On-board Bottom-up-Pantograph typically for bus charging
        PANTOGRAPH_TOP_DOWN = "PANTOGRAPH_TOP_DOWN"  # Off-board Top-down-Pantograph typically for bus charging
        SAE_J3400 = "SAE_J3400"  # SAE J3400, also known as North American Charging Standard (NACS), developed by Tesla, Inc in 2021.
        TESLA_R = "TESLA_R"  # Tesla Connector "Roadster"-type (round, 4 pin)
        TESLA_S = "TESLA_S"  # Tesla Connector "Model-S"-type (oval, 5 pin). Mechanically compatible with SAE J3400 but uses CAN bus for communication instead of power line communication.
        UNKNOWN = "UNKNOWN"

        @classmethod
        def _missing_(cls, key):
            return cls.UNKNOWN

    class ConnectorFormat(enum.StrEnum):
        SOCKET = "SOCKET"
        CABLE = "CABLE"

    class PowerType(enum.StrEnum):
        AC_1_PHASE = "AC_1_PHASE"
        AC_2_PHASE = "AC_2_PHASE"
        AC_2_PHASE_SPLIT = "AC_2_PHASE_SPLIT"
        AC_3_PHASE = "AC_3_PHASE"
        DC = "DC"
        UNKNOWN = "UNKNOWN"

        @classmethod
        def _missing_(cls, key):
            return cls.UNKNOWN

    id: str | int
    standard: ConnectorType
    format: ConnectorFormat | None = None
    max_voltage: int | None = None
    max_amperage: int | None = None
    voltage: int | None = None
    amperage: int | None = None
    power_type: PowerType | None = None
    max_electric_power: int | None = None

    # TODO: tariff_ids

    last_updated: datetime.datetime

    def max_power(self) -> int:
        if self.max_electric_power is not None:
            return self.max_electric_power

        match self.power_type:
            case OcpiConnector.PowerType.AC_3_PHASE:
                power_factor = sqrt(3)
            case OcpiConnector.PowerType.AC_1_PHASE | OcpiConnector.PowerType.DC:
                power_factor = 1
            case None:
                return 0
            case _:
                raise NotImplementedError(
                    "power calculation for 2 phases not implemented"
                )

        voltage = self.max_voltage or self.voltage
        amperage = self.max_amperage or self.amperage
        return voltage * amperage * power_factor

    def convert(self) -> Connector:
        return Connector(
            id_from_source=str(self.id),
            connector_type=connector_mapping[self.standard],
            connector_format=format_mapping[self.format] if self.format else "",
            max_power=self.max_power(),
        )


connector_mapping = {
    OcpiConnector.ConnectorType.CHADEMO: Connector.ConnectorTypes.CHADEMO,
    OcpiConnector.ConnectorType.DOMESTIC_E: Connector.ConnectorTypes.DOMESTIC_E,
    OcpiConnector.ConnectorType.DOMESTIC_F: Connector.ConnectorTypes.SCHUKO,
    OcpiConnector.ConnectorType.IEC_60309_2_SINGLE_16: Connector.ConnectorTypes.CEE_SINGLE_16,
    OcpiConnector.ConnectorType.IEC_60309_2_THREE_16: Connector.ConnectorTypes.CEE_THREE_16,
    OcpiConnector.ConnectorType.IEC_60309_2_THREE_32: Connector.ConnectorTypes.CEE_THREE_32,
    OcpiConnector.ConnectorType.IEC_60309_2_THREE_64: Connector.ConnectorTypes.CEE_THREE_64,
    OcpiConnector.ConnectorType.IEC_62196_T1: Connector.ConnectorTypes.TYPE_1,
    OcpiConnector.ConnectorType.IEC_62196_T1_COMBO: Connector.ConnectorTypes.CCS_TYPE_1,
    OcpiConnector.ConnectorType.IEC_62196_T2: Connector.ConnectorTypes.TYPE_2,
    OcpiConnector.ConnectorType.IEC_62196_T2_COMBO: Connector.ConnectorTypes.CCS_TYPE_2,
    OcpiConnector.ConnectorType.IEC_62196_T3A: Connector.ConnectorTypes.TYPE_3A,
    OcpiConnector.ConnectorType.IEC_62196_T3C: Connector.ConnectorTypes.TYPE_3C,
    OcpiConnector.ConnectorType.SAE_J3400: Connector.ConnectorTypes.NACS,
    OcpiConnector.ConnectorType.TESLA_S: Connector.ConnectorTypes.NACS,
    OcpiConnector.ConnectorType.TESLA_R: Connector.ConnectorTypes.TESLA_ROADSTER_HPC,
    OcpiConnector.ConnectorType.UNKNOWN: Connector.ConnectorTypes.OTHER,
}

format_mapping = {
    OcpiConnector.ConnectorFormat.SOCKET: Connector.ConnectorFormats.SOCKET,
    OcpiConnector.ConnectorFormat.CABLE: Connector.ConnectorFormats.CABLE,
}


class OcpiEvse(Schema):
    class OcpiEvseStatus(enum.StrEnum):
        AVAILABLE = "AVAILABLE"
        BLOCKED = "BLOCKED"
        CHARGING = "CHARGING"
        INOPERATIVE = "INOPERATIVE"
        OUTOFORDER = "OUTOFORDER"
        PLANNED = "PLANNED"
        REMOVED = "REMOVED"
        RESERVED = "RESERVED"
        UNKNOWN = "UNKNOWN"

        @classmethod
        def _missing_(cls, value):
            return cls.UNKNOWN

    uid: str | int
    evse_id: str | None = None
    physical_reference: str | None = None
    status: OcpiEvseStatus
    # TODO: status_schedule
    connectors: list[OcpiConnector] | None = None

    last_updated: datetime.datetime

    def convert(
        self, ignore_evseid: bool = False, uid_as_evseid: bool = False
    ) -> Chargepoint:
        return Chargepoint(
            id_from_source=str(self.uid),
            evseid=none_to_blank(self.get_evseid(ignore_evseid, uid_as_evseid)),
            physical_reference=none_to_blank(self.physical_reference),
        )

    def convert_status(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: str | None = None,
        time_zone: str | None = None,
    ) -> CurrentStatus:
        return CurrentStatus(
            status=status_mapping[self.status],
            timestamp=(
                timezone(time_zone).localize(self.last_updated)
                if time_zone is not None and self.last_updated.tzinfo is None
                else self.last_updated
            ),
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=(
                license_attribution_link if license_attribution_link is not None else ""
            ),
        )

    def get_evseid(
        self, ignore_evseids: bool = False, uid_as_evseid: bool = False
    ) -> str | None:
        if self.evse_id is not None and not ignore_evseids:
            return normalize_evseid(self.evse_id)
        elif uid_as_evseid:
            try:
                id = normalize_evseid(self.uid)
                validate_evseid(id)
                return id
            except ValidationError:
                return None
        else:
            return None


INVALID_STATUSES = [OcpiEvse.OcpiEvseStatus.REMOVED, OcpiEvse.OcpiEvseStatus.PLANNED]


class PatchOcpiEvse(Schema):
    status: OcpiEvse.OcpiEvseStatus
    last_updated: datetime.datetime


status_mapping = {
    OcpiEvse.OcpiEvseStatus.AVAILABLE: CurrentStatus.Status.AVAILABLE,
    OcpiEvse.OcpiEvseStatus.BLOCKED: CurrentStatus.Status.BLOCKED,
    OcpiEvse.OcpiEvseStatus.CHARGING: CurrentStatus.Status.CHARGING,
    OcpiEvse.OcpiEvseStatus.INOPERATIVE: CurrentStatus.Status.INOPERATIVE,
    OcpiEvse.OcpiEvseStatus.OUTOFORDER: CurrentStatus.Status.OUTOFORDER,
    OcpiEvse.OcpiEvseStatus.PLANNED: CurrentStatus.Status.PLANNED,
    OcpiEvse.OcpiEvseStatus.REMOVED: CurrentStatus.Status.REMOVED,
    OcpiEvse.OcpiEvseStatus.RESERVED: CurrentStatus.Status.RESERVED,
    OcpiEvse.OcpiEvseStatus.UNKNOWN: CurrentStatus.Status.UNKNOWN,
}


class GeoLocation(Schema):
    longitude: float
    latitude: float


class OcpiOperator(Schema):
    name: str


class OcpiLocation(Schema):
    id: str | int
    country: str | None = None
    country_code: str | None = None
    name: str | None = None
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    state: str | None = None
    coordinates: GeoLocation | None = None
    evses: list[OcpiEvse] | None = None
    operator: OcpiOperator | None = None
    suboperator: OcpiOperator | None = None
    time_zone: str | None = None

    # TODO: opening_times

    last_updated: datetime.datetime

    def convert(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: str | None = None,
        with_status: bool = False,
        ignore_evseids: bool = False,
        uid_as_evseid: bool = False,
    ) -> ChargingSiteItem:
        evse_id = next(
            (
                evse.get_evseid(ignore_evseids, uid_as_evseid)
                for evse in self.evses
                if evse.get_evseid(ignore_evseids, uid_as_evseid)
            ),
            None,
        )
        if evse_id:
            operator_id = normalize_evseid(evse_id)[:5]
            network, _ = Network.get_or_create(
                evse_operator_id=none_to_blank(operator_id),
                defaults={
                    "name": none_to_blank(
                        self.operator.name if self.operator is not None else None
                    )
                },
            )
        else:
            network = None

        site = ChargingSite(
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=(
                license_attribution_link if license_attribution_link is not None else ""
            ),
            id_from_source=str(self.id),
            name=none_to_blank(self.name if self.name is not None else self.address),
            location=Point(self.coordinates.longitude, self.coordinates.latitude),
            network=network,
            operator=(
                none_to_blank(self.suboperator.name)
                if self.suboperator is not None
                else ""
            ),
            street=none_to_blank(self.address),
            zipcode=none_to_blank(self.postal_code),
            city=none_to_blank(self.city),
            country=self.country if self.country is not None else self.country_code,
        )
        chargepoints = []
        for evse in self.evses:
            if evse.connectors is not None and evse.status not in INVALID_STATUSES:
                con_ids = set()
                connectors = []
                for con in evse.connectors:
                    if con.id in con_ids:
                        logger.warning(
                            "Duplicate connector ID %s for EVSE %s",
                            con.id,
                            evse.get_evseid(ignore_evseids, uid_as_evseid),
                        )
                        continue
                    con_ids.add(con.id)
                    connectors.append(con.convert())
                status = (
                    evse.convert_status(
                        data_source,
                        license_attribution,
                        license_attribution_link,
                        self.time_zone,
                    )
                    if with_status
                    else None
                )
                chargepoints.append(
                    ChargepointItem(
                        evse.convert(ignore_evseids, uid_as_evseid), connectors, status
                    )
                )
        return ChargingSiteItem(site, chargepoints)

    def is_valid(self):
        return self.evses is not None and any(
            evse.status != OcpiEvse.OcpiEvseStatus.REMOVED for evse in self.evses
        )

    def convert_status(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: str | None = None,
    ) -> Iterable[RealtimeStatusItem]:
        for evse in self.evses:
            yield RealtimeStatusItem(
                site_id_from_source=self.id,
                chargepoint_id_from_source=evse.uid,
                status=evse.convert_status(
                    data_source,
                    license_attribution,
                    license_attribution_link,
                    self.time_zone,
                ),
            )
