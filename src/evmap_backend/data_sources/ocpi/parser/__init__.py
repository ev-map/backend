import datetime
import enum
import logging
from dataclasses import dataclass
from math import sqrt
from re import match
from typing import Iterable, List, Optional, Tuple, Union

from django.contrib.gis.geos import Point
from tqdm import tqdm

from evmap_backend.chargers.fields import normalize_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector
from evmap_backend.helpers.database import none_to_blank
from evmap_backend.realtime.models import RealtimeStatus

# spec: https://evroaming.org/wp-content/uploads/2025/02/OCPI-2.3.0.pdf


@dataclass
class OcpiConnector:
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
    max_voltage: int
    max_amperage: int
    power_type: PowerType
    max_electric_power: Optional[int]

    # TODO: tariff_ids

    last_updated: datetime.datetime

    @classmethod
    def from_json(cls, data: dict):
        return OcpiConnector(
            id=data["id"],
            standard=OcpiConnector.ConnectorType(data["standard"]),
            format=OcpiConnector.ConnectorFormat(data["format"]),
            max_voltage=(
                data["max_voltage"] if "max_voltage" in data else data["voltage"]
            ),
            max_amperage=(
                data["max_amperage"] if "max_amperage" in data else data["amperage"]
            ),
            power_type=OcpiConnector.PowerType(data["power_type"]),
            max_electric_power=data.get("max_electric_power"),
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
        )

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

        return self.max_voltage * self.max_amperage * power_factor

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


@dataclass
class OcpiEvse:
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
    status: OcpiEvseStatus
    # TODO: status_schedule
    connectors: List[OcpiConnector]

    last_updated: datetime.datetime

    @classmethod
    def from_json(cls, data: dict, status_only: bool = False):
        if "connectors" not in data and not status_only:
            raise ValueError("OCPI EVSE has no connectors")

        return OcpiEvse(
            uid=data["uid"],
            evse_id=data.get("evse_id"),
            status=(
                OcpiEvse.OcpiEvseStatus(data["status"])
                if data["status"] in OcpiEvse.OcpiEvseStatus
                else OcpiEvse.OcpiEvseStatus.UNKNOWN
            ),
            connectors=(
                [OcpiConnector.from_json(connector) for connector in data["connectors"]]
                if "connectors" in data
                else None
            ),
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
        )

    def convert(self) -> Chargepoint:
        return Chargepoint(
            id_from_source=self.uid,
            evseid=normalize_evseid(self.evse_id) if self.evse_id is not None else "",
        )


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


@dataclass
class OcpiLocation:
    id: str
    country_code: Optional[str]
    name: Optional[str]
    address: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    state: Optional[str]
    coordinates: Optional[Tuple[float, float]]
    evses: List[OcpiEvse]
    operator_name: Optional[str]

    # TODO: opening_times

    last_updated: datetime.datetime

    @classmethod
    def from_json(cls, data: dict, status_only: bool = False):
        if (
            "coordinates" not in data or "country_code" not in data
        ) and not status_only:
            logging.warning(f"OCPI location with missing required fields: {data}")
            return None

        return OcpiLocation(
            data["id"],
            data.get("country_code"),
            data.get("name"),
            data.get("address"),
            data.get("city"),
            data.get("postal_code"),
            data.get("state"),
            (
                (
                    float(data["coordinates"]["longitude"]),
                    float(data["coordinates"]["latitude"]),
                )
                if "coordinates" in data
                else None
            ),
            [OcpiEvse.from_json(evse, status_only) for evse in data["evses"]],
            data["operator"]["name"] if "operator" in data else None,
            datetime.datetime.fromisoformat(data["last_updated"]),
        )

    def convert(
        self, data_source: str
    ) -> Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]:
        site = ChargingSite(
            data_source=data_source,
            id_from_source=self.id,
            name=none_to_blank(self.name if self.name is not None else self.address),
            location=Point(*self.coordinates),
            network=self.operator_name,
            street=none_to_blank(self.address),
            zipcode=none_to_blank(self.postal_code),
            city=none_to_blank(self.city),
            country=self.country_code,
        )
        chargepoints = [
            (rp.convert(), [con.convert() for con in rp.connectors])
            for rp in self.evses
        ]
        return site, chargepoints

    def convert_status(self, data_source: str) -> List[Tuple[str, RealtimeStatus]]:
        return [
            (
                self.id,
                RealtimeStatus(
                    chargepoint=evse.convert(),
                    status=status_mapping[evse.status],
                    timestamp=evse.last_updated,
                    data_source=data_source,
                ),
            )
            for evse in self.evses
        ]


class OcpiParser:
    def parse_locations(
        self, data: Iterable, status_only: bool = False
    ) -> Iterable[OcpiLocation]:
        for site in tqdm(data):
            loc = OcpiLocation.from_json(site, status_only)
            if loc is not None:
                yield loc
