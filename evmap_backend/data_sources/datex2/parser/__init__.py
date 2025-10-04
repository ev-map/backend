import enum
from dataclasses import dataclass
from typing import Dict, List, Tuple

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError

from evmap_backend.chargers.fields import EVSEIDType, normalize_evseid, validate_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector


@dataclass
class Datex2MultilingualString:
    values: Dict[str, str]

    def first(self) -> str:
        return next(iter(self.values.values()))


@dataclass
class Datex2Connector:
    class ConnectorType(enum.StrEnum):
        CHADEMO = "chademo"
        CEE3 = "cee3"
        CEE5 = "cee5"
        YAZAKI = "yazaki"
        DOMESTIC = "domestic"
        DOMESTIC_A = "domesticA"
        DOMESTIC_B = "domesticB"
        DOMESTIC_C = "domesticC"
        DOMESTIC_D = "domesticD"
        DOMESTIC_E = "domesticE"
        DOMESTIC_F = "domesticF"
        DOMESTIC_G = "domesticG"
        DOMESTIC_H = "domesticH"
        DOMESTIC_I = "domesticI"
        DOMESTIC_J = "domesticJ"
        DOMESTIC_K = "domesticK"
        DOMESTIC_L = "domesticL"
        DOMESTIC_M = "domesticM"
        DOMESTIC_N = "domesticN"
        DOMESTIC_O = "domesticO"
        IEC60309_2_SINGLE_16 = "iec60309x2single16"
        IEC60309_2_THREE_16 = "iec60309x2three16"
        IEC60309_2_THREE_32 = "iec60309x2three32"
        IEC60309_2_THREE_64 = "iec60309x2three64"
        TYPE_1 = "iec62196T1"
        CCS_TYPE_1 = "iec62196T1COMBO"
        TYPE_2 = "iec62196T2"
        CCS_TYPE_2 = "iec62196T2COMBO"
        TYPE_3A = "iec62196T3A"
        TYPE_3C = "iec62196T3C"
        PANTOGRAPH_BOTTOM_UP = "pantographBottomUp"
        PANTOGRAPH_TOP_DOWN = "pantographTopDown"
        TESLA_CONNECTOR_EUROPE = "teslaConnectorEurope"
        NACS = "teslaConnectorAmerica"
        TESLA_R = "teslaR"
        TESLA_S = "teslaS"
        OTHER = "other"

    class ChargingMode(enum.StrEnum):
        MODE_1_AC_1P = "mode1AC1p"
        MODE_1_AC_3P = "mode1AC3p"
        MODE_2_AC_1P = "mode2AC1p"
        MODE_2_AC_3P = "mode2AC3p"
        MODE_3_AC_3P = "mode3AC3p"
        MODE_4_DC = "mode4DC"
        LEGACY_INDUCTIVE = "legacyInductive"
        CCS = "ccs"
        OTHER = "other"
        UNKNOWN = "unknown"

    connector_type: ConnectorType
    max_power: float
    charging_mode: ChargingMode = None

    def convert(self) -> Connector:
        return Connector(
            connector_type=connector_mapping.get(
                self.connector_type, Connector.ConnectorTypes.OTHER
            ),
            max_power=self.max_power,
        )


connector_mapping = {
    Datex2Connector.ConnectorType.CHADEMO: Connector.ConnectorTypes.CHADEMO,
    Datex2Connector.ConnectorType.DOMESTIC_F: Connector.ConnectorTypes.SCHUKO,
    Datex2Connector.ConnectorType.IEC60309_2_SINGLE_16: Connector.ConnectorTypes.CEE_SINGLE_16,
    Datex2Connector.ConnectorType.IEC60309_2_THREE_16: Connector.ConnectorTypes.CEE_THREE_16,
    Datex2Connector.ConnectorType.IEC60309_2_THREE_32: Connector.ConnectorTypes.CEE_THREE_32,
    Datex2Connector.ConnectorType.IEC60309_2_THREE_64: Connector.ConnectorTypes.CEE_THREE_64,
    Datex2Connector.ConnectorType.TYPE_1: Connector.ConnectorTypes.TYPE_1,
    Datex2Connector.ConnectorType.CCS_TYPE_1: Connector.ConnectorTypes.CCS_TYPE_1,
    Datex2Connector.ConnectorType.TYPE_2: Connector.ConnectorTypes.TYPE_2,
    Datex2Connector.ConnectorType.CCS_TYPE_2: Connector.ConnectorTypes.CCS_TYPE_2,
    Datex2Connector.ConnectorType.TYPE_3A: Connector.ConnectorTypes.TYPE_3A,
    Datex2Connector.ConnectorType.TYPE_3C: Connector.ConnectorTypes.TYPE_3C,
    Datex2Connector.ConnectorType.TESLA_CONNECTOR_EUROPE: Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
    Datex2Connector.ConnectorType.NACS: Connector.ConnectorTypes.NACS,
    Datex2Connector.ConnectorType.TESLA_R: Connector.ConnectorTypes.TESLA_ROADSTER_HPC,
}


@dataclass
class Datex2RefillPoint:
    id: str
    connectors: List[Datex2Connector]
    external_identifier: str = None

    def convert(self) -> Chargepoint:
        evseid = ""
        try:
            id = normalize_evseid(
                self.external_identifier if self.external_identifier else ""
            )
            validate_evseid(id, EVSEIDType.EVSE)
            evseid = id
        except ValidationError:
            try:
                id = normalize_evseid(self.id)
                validate_evseid(id, EVSEIDType.EVSE)
                evseid = id
            except ValidationError:
                pass

        return Chargepoint(id_from_source=self.id, evseid=evseid)


@dataclass
class Datex2EnergyInfrastructureSite:
    id: str
    name: Datex2MultilingualString
    # TODO: operatingHours
    location: Tuple[float, float]
    # TODO: address
    operator_name: Datex2MultilingualString
    operator_phone: str
    refill_points: List[Datex2RefillPoint]
    additional_information: Datex2MultilingualString = None

    def convert(self, data_source: str) -> ChargingSite:
        return ChargingSite(
            data_source=data_source,
            id_from_source=self.id,
            name=(
                self.name.first()
                if self.name
                else (
                    self.additional_information.first()
                    if self.additional_information
                    else ""
                )
            ),
            location=Point(*self.location),
            operator=self.operator_name.first(),
        )
