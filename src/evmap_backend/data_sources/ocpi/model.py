import datetime
import enum
import logging
from math import sqrt
from typing import Generic, List, Optional, Tuple, TypeVar

from django.contrib.gis.geos import Point
from ninja import Schema
from pytz import timezone

from evmap_backend import settings
from evmap_backend.chargers.fields import normalize_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.helpers.database import none_to_blank
from evmap_backend.realtime.models import RealtimeStatus

# OCPI spec: https://evroaming.org/wp-content/uploads/2025/02/OCPI-2.3.0.pdf

DataT = TypeVar("DataT")


class OcpiResponse(Schema, Generic[DataT]):
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
    endpoints: List[OcpiEndpoint]


class OcpiImage(Schema):
    url: str
    thumbnail: str = None
    category: str
    type: str
    width: int = None
    height: int = None


class OcpiBusinessDetails(Schema):
    name: str
    website: Optional[str] = None
    logo: Optional[OcpiImage] = None


class OcpiCredentialsRole(Schema):
    role: str
    party_id: str
    country_code: str
    business_details: OcpiBusinessDetails


class OcpiCredentials22(Schema):
    token: str
    url: str
    hub_party_id: Optional[str] = None
    roles: List[OcpiCredentialsRole]


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

    class ConnectorFormat(enum.StrEnum):
        SOCKET = "SOCKET"
        CABLE = "CABLE"

    class PowerType(enum.StrEnum):
        AC_1_PHASE = "AC_1_PHASE"
        AC_2_PHASE = "AC_2_PHASE"
        AC_2_PHASE_SPLIT = "AC_2_PHASE_SPLIT"
        AC_3_PHASE = "AC_3_PHASE"
        DC = "DC"

    id: str
    standard: ConnectorType
    format: ConnectorFormat
    max_voltage: Optional[int] = None
    max_amperage: Optional[int] = None
    voltage: Optional[int] = None
    amperage: Optional[int] = None
    power_type: PowerType
    max_electric_power: Optional[int] = None

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
            case _:
                raise NotImplementedError(
                    "power calculation for 2 phases not implemented"
                )

        voltage = self.max_voltage or self.voltage
        amperage = self.max_amperage or self.amperage
        return voltage * amperage * power_factor

    def convert(self) -> Connector:
        return Connector(
            id_from_source=self.id,
            connector_type=connector_mapping.get(self.standard),
            connector_format=format_mapping[self.format],
            max_power=self.max_power(),
        )


connector_mapping = {
    OcpiConnector.ConnectorType.CHADEMO: Connector.ConnectorTypes.CHADEMO,
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

    uid: str
    evse_id: str
    physical_reference: Optional[str] = None
    status: OcpiEvseStatus
    # TODO: status_schedule
    connectors: Optional[List[OcpiConnector]] = None

    last_updated: datetime.datetime

    def convert(self) -> Chargepoint:
        return Chargepoint(
            id_from_source=self.uid,
            evseid=normalize_evseid(self.evse_id) if self.evse_id is not None else "",
            physical_reference=none_to_blank(self.physical_reference),
        )


class PatchOcpiEvse(Schema):
    status: OcpiEvse.OcpiEvseStatus
    last_updated: datetime.datetime


status_mapping = {
    OcpiEvse.OcpiEvseStatus.AVAILABLE: RealtimeStatus.Status.AVAILABLE,
    OcpiEvse.OcpiEvseStatus.BLOCKED: RealtimeStatus.Status.BLOCKED,
    OcpiEvse.OcpiEvseStatus.CHARGING: RealtimeStatus.Status.CHARGING,
    OcpiEvse.OcpiEvseStatus.INOPERATIVE: RealtimeStatus.Status.INOPERATIVE,
    OcpiEvse.OcpiEvseStatus.OUTOFORDER: RealtimeStatus.Status.OUTOFORDER,
    OcpiEvse.OcpiEvseStatus.PLANNED: RealtimeStatus.Status.PLANNED,
    OcpiEvse.OcpiEvseStatus.REMOVED: RealtimeStatus.Status.REMOVED,
    OcpiEvse.OcpiEvseStatus.RESERVED: RealtimeStatus.Status.RESERVED,
    OcpiEvse.OcpiEvseStatus.UNKNOWN: RealtimeStatus.Status.UNKNOWN,
}


class GeoLocation(Schema):
    longitude: float
    latitude: float


class OcpiOperator(Schema):
    name: str


class OcpiLocation(Schema):
    id: str
    country: Optional[str] = None
    country_code: Optional[str] = None
    name: Optional[str]
    address: Optional[str]
    city: Optional[str]
    postal_code: Optional[str] = None
    state: Optional[str] = None
    coordinates: Optional[GeoLocation]
    evses: Optional[List[OcpiEvse]] = None
    operator: Optional[OcpiOperator] = None
    suboperator: Optional[OcpiOperator] = None
    time_zone: Optional[str] = None

    # TODO: opening_times

    last_updated: datetime.datetime

    def convert(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: Optional[str] = None,
    ) -> Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]:
        operator_id = normalize_evseid(self.evses[0].evse_id)[:5]
        network, _ = Network.objects.get_or_create(
            evse_operator_id=none_to_blank(operator_id),
            defaults=dict(
                name=none_to_blank(
                    self.operator.name if self.operator is not None else None
                )
            ),
        )

        site = ChargingSite(
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=(
                license_attribution_link if license_attribution_link is not None else ""
            ),
            id_from_source=self.id,
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
            if evse.connectors is not None:
                con_ids = set()
                connectors = []
                for con in evse.connectors:
                    if con.id in con_ids:
                        logging.warning(
                            "Duplicate connector ID %s for EVSE %s",
                            con.id,
                            evse.evse_id,
                        )
                        continue
                    con_ids.add(con.id)
                    connectors.append(con.convert())
                chargepoints.append((evse.convert(), connectors))
        return site, chargepoints

    def is_valid(self):
        return self.evses is not None and any(
            evse.status != OcpiEvse.OcpiEvseStatus.REMOVED for evse in self.evses
        )

    def convert_status(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: Optional[str] = None,
    ) -> List[Tuple[str, RealtimeStatus]]:
        return [
            (
                self.id,
                RealtimeStatus(
                    chargepoint=evse.convert(),
                    status=status_mapping[evse.status],
                    timestamp=(
                        timezone(self.time_zone).localize(evse.last_updated)
                        if self.time_zone is not None
                        and evse.last_updated.tzinfo is None
                        else evse.last_updated
                    ),
                    data_source=data_source,
                    license_attribution=license_attribution,
                    license_attribution_link=(
                        license_attribution_link
                        if license_attribution_link is not None
                        else ""
                    ),
                ),
            )
            for evse in self.evses
        ]
