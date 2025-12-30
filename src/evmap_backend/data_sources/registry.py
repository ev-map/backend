from typing import Dict, List, Type

from evmap_backend.data_sources import DataSource
from evmap_backend.data_sources.datex2.source import (
    Datex2AustriaDataSource,
    Datex2AustriaRealtimeDataSource,
    Datex2LuxembourgEcoMovementDataSource,
    Datex2MobilithekEcoMovementDatex2DataSource,
    Datex2MobilithekEcoMovementRealtimeDataSource,
    Datex2MobilithekEnbwDataSource,
    Datex2MobilithekEnbwRealtimeDataSource,
    Datex2MobilithekLadenetzDataSource,
    Datex2MobilithekLadenetzRealtimeDataSource,
    Datex2MobilithekUlmDataSource,
    Datex2MobilithekUlmRealtimeDataSource,
    Datex2MobilithekWirelaneDataSource,
    Datex2MobilithekWirelaneRealtimeDataSource,
)
from evmap_backend.data_sources.eliso.source import ElisoDataSource
from evmap_backend.data_sources.monta.source import MontaDataSource
from evmap_backend.data_sources.nobil.source import (
    NobilDataSource,
    NobilRealtimeDataSource,
)
from evmap_backend.data_sources.ocpi.source import (
    BlinkUkOcpiDataSource,
    BlinkUkOcpiRealtimeDataSource,
    BpPulseUkOcpiDataSource,
    BpPulseUkOcpiRealtimeDataSource,
    ChargyUkOcpiDataSource,
    EsbUkOcpiDataSource,
    EsbUkOcpiRealtimeDataSource,
    IonityUkOcpiDataSource,
    IonityUkOcpiRealtimeDataSource,
    MfgUkOcpiDataSource,
    NdwNetherlandsOcpiDataSource,
)

DATA_SOURCE_REGISTRY: Dict[str, Type[DataSource]] = {
    # Austria
    "e-control_austria": Datex2AustriaDataSource,
    "e-control_austria_realtime": Datex2AustriaRealtimeDataSource,
    # Germany
    "monta": MontaDataSource,
    "mobilithek_eliso": ElisoDataSource,
    "mobilithek_ecomovement": Datex2MobilithekEcoMovementDatex2DataSource,
    "mobilithek_ecomovement_realtime": Datex2MobilithekEcoMovementRealtimeDataSource,
    "mobilithek_enbw": Datex2MobilithekEnbwDataSource,
    "mobilithek_enbw_realtime": Datex2MobilithekEnbwRealtimeDataSource,
    "mobilithek_ladenetz": Datex2MobilithekLadenetzDataSource,
    "mobilithek_ladenetz_realtime": Datex2MobilithekLadenetzRealtimeDataSource,
    "mobilithek_ulm": Datex2MobilithekUlmDataSource,
    "mobilithek_ulm_realtime": Datex2MobilithekUlmRealtimeDataSource,
    "mobilithek_wirelane": Datex2MobilithekWirelaneDataSource,
    "mobilithek_wirelane_realtime": Datex2MobilithekWirelaneRealtimeDataSource,
    # Luxembourg
    "luxembourg_ecomovement": Datex2LuxembourgEcoMovementDataSource,
    # Netherlands
    "ndw_netherlands": NdwNetherlandsOcpiDataSource,
    # Sweden and Norway
    "nobil": NobilDataSource,
    "nobil_realtime": NobilRealtimeDataSource,
    # United Kingdom
    "bp_pulse_uk": BpPulseUkOcpiDataSource,
    "bp_pulse_uk_realtime": BpPulseUkOcpiRealtimeDataSource,
    "ionity_uk": IonityUkOcpiDataSource,
    "ionity_uk_realtime": IonityUkOcpiRealtimeDataSource,
    "blink_uk": BlinkUkOcpiDataSource,
    "blink_uk_realtime": BlinkUkOcpiRealtimeDataSource,
    "esb_uk": EsbUkOcpiDataSource,
    "esb_uk_realtime": EsbUkOcpiRealtimeDataSource,
    "chargy_uk": ChargyUkOcpiDataSource,
    "mfg_uk": MfgUkOcpiDataSource,
}


def get_data_source(source_id: str) -> DataSource:
    """Get a data source instance by ID"""
    if source_id not in DATA_SOURCE_REGISTRY:
        raise ValueError(
            f"Unknown data source: {source_id}. Available sources: {', '.join(DATA_SOURCE_REGISTRY.keys())}"
        )

    return DATA_SOURCE_REGISTRY[source_id]()


def list_available_sources() -> List[str]:
    """List all available data source IDs"""
    return list(DATA_SOURCE_REGISTRY.keys())
