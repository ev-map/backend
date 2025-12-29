import datetime
import enum
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Union

from django.contrib.gis.geos import Point
from tqdm import tqdm

from evmap_backend.chargers.fields import normalize_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector

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

    class OcpiConnectorFormat(enum.StrEnum):
        SOCKET = "SOCKET"
        CABLE = "CABLE"

    id: str
    standard: ConnectorType
    format: OcpiConnectorFormat
    max_voltage: int
    max_amperage: int
    max_electric_power: Optional[int]

    # TODO: tariff_ids

    last_updated: datetime.datetime

    @classmethod
    def from_json(cls, data: dict):
        return OcpiConnector(
            id=data["id"],
            standard=data["standard"],
            format=data["format"],
            max_voltage=data["max_voltage"],
            max_amperage=data["max_amperage"],
            max_electric_power=data["max_electric_power"],
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
        )

    def convert(self) -> Connector:
        return Connector(
            id_from_source=self.id,
            connector_type=connector_mapping.get(self.standard),
            connector_format=format_mapping[self.format],
            max_power=(
                self.max_electric_power
                if self.max_electric_power is not None
                else self.max_voltage * self.max_amperage
            ),
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
    OcpiConnector.ConnectorType.TESLA_R: Connector.ConnectorTypes.TESLA_ROADSTER_HPC,
}

format_mapping = {
    OcpiConnector.OcpiConnectorFormat.SOCKET: Connector.ConnectorFormats.SOCKET,
    OcpiConnector.OcpiConnectorFormat.CABLE: Connector.ConnectorFormats.CABLE,
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
    def from_json(cls, data: dict):
        return OcpiEvse(
            uid=data["uid"],
            evse_id=data["evse_id"],
            status=OcpiEvse.OcpiEvseStatus(data["status"]),
            connectors=[
                OcpiConnector.from_json(connector) for connector in data["connectors"]
            ],
            last_updated=datetime.datetime.fromisoformat(data["last_updated"]),
        )

    def convert(self) -> Chargepoint:
        return Chargepoint(
            id_from_source=self.uid,
            evseid=normalize_evseid(self.evse_id) if self.evse_id is not None else "",
        )


@dataclass
class OcpiLocation:
    id: str
    country_code: str
    name: str
    address: str
    city: str
    postal_code: str
    state: str
    coordinates: Tuple[float, float]
    evses: List[OcpiEvse]
    operator_name: str

    # TODO: opening_times

    last_updated: datetime.datetime

    @classmethod
    def from_json(cls, data: dict):
        return OcpiLocation(
            data["id"],
            data["country_code"],
            data["name"],
            data["address"],
            data["city"],
            data["postal_code"],
            data["state"],
            (
                float(data["coordinates"]["longitude"]),
                float(data["coordinates"]["latitude"]),
            ),
            [OcpiEvse.from_json(evse) for evse in data["evses"]],
            data["operator"]["name"],
            datetime.datetime.fromisoformat(data["last_updated"]),
        )

    def convert(
        self, data_source: str
    ) -> Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]:
        site = ChargingSite(
            data_source=data_source,
            id_from_source=self.id,
            name=self.name if self.name is not None else self.address,
            location=Point(*self.coordinates),
            operator=self.operator_name,
            street=self.address,
            zipcode=self.postal_code,
            city=self.city,
            country=self.country_code,
        )
        chargepoints = [
            (rp.convert(), [con.convert() for con in rp.connectors])
            for rp in self.evses
        ]
        return site, chargepoints


class OcpiParser:
    def parse(self, data: Iterable) -> Iterable[OcpiLocation]:
        for site in tqdm(data):
            yield OcpiLocation.from_json(site)
