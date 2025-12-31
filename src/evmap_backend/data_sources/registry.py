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
from evmap_backend.data_sources.goingelectric.source import GoingElectricDataSource
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

DATA_SOURCE_CLASSES: List[Type[DataSource]] = [
    # multiple countries
    GoingElectricDataSource,
    # Austria
    Datex2AustriaDataSource,
    Datex2AustriaRealtimeDataSource,
    # Germany
    MontaDataSource,
    ElisoDataSource,
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
    # Luxembourg
    Datex2LuxembourgEcoMovementDataSource,
    # Netherlands
    NdwNetherlandsOcpiDataSource,
    # Sweden and Norway
    NobilDataSource,
    NobilRealtimeDataSource,
    # United Kingdom
    BpPulseUkOcpiDataSource,
    BpPulseUkOcpiRealtimeDataSource,
    IonityUkOcpiDataSource,
    IonityUkOcpiRealtimeDataSource,
    BlinkUkOcpiDataSource,
    BlinkUkOcpiRealtimeDataSource,
    EsbUkOcpiDataSource,
    EsbUkOcpiRealtimeDataSource,
    ChargyUkOcpiDataSource,
    MfgUkOcpiDataSource,
    # Latvia
    # LatviaOcpiDataSource,  # Data is malformed (duplicate IDs)
]

DATA_SOURCE_REGISTRY: Dict[str, Type[DataSource]] = {
    cls.id: cls for cls in DATA_SOURCE_CLASSES
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
