import sys
from typing import Dict, List, Type

from evmap_backend.data_sources import DataSource
from evmap_backend.data_sources.datex2.source import (
    Datex2AustriaDataSource,
    Datex2AustriaRealtimeDataSource,
    Datex2BelgiumEcoMovementDataSource,
    Datex2DenmarkEcoMovementDataSource,
    Datex2LuxembourgEcoMovementDataSource,
    Datex2MobilithekEcoMovementDatex2DataSource,
    Datex2MobilithekEcoMovementRealtimeDataSource,
    Datex2MobilithekEluMobilityDataSource,
    Datex2MobilithekEluMobilityRealtimeDataSource,
    Datex2MobilithekEnbwDataSource,
    Datex2MobilithekEnbwRealtimeDataSource,
    Datex2MobilithekEroundDataSource,
    Datex2MobilithekEroundRealtimeDataSource,
    Datex2MobilithekLadenetzDataSource,
    Datex2MobilithekLadenetzRealtimeDataSource,
    Datex2MobilithekM8MitDataSource,
    Datex2MobilithekM8MitRealtimeDataSource,
    Datex2MobilithekMontaDataSource,
    Datex2MobilithekMontaRealtimeDataSource,
    Datex2MobilithekPumpDataSource,
    Datex2MobilithekQwelloDataSource,
    Datex2MobilithekQwelloRealtimeDataSource,
    Datex2MobilithekSmatricsDataSource,
    Datex2MobilithekSmatricsRealtimeDataSource,
    Datex2MobilithekTeslaDataSource,
    Datex2MobilithekTeslaRealtimeDataSource,
    Datex2MobilithekUlmDataSource,
    Datex2MobilithekUlmRealtimeDataSource,
    Datex2MobilithekWirelaneDataSource,
    Datex2MobilithekWirelaneRealtimeDataSource,
    Datex2SloveniaDataSource,
    Datex2SloveniaRealtimeDataSource,
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
    CommunityByShellRechargeUkOcpiDataSource,
    CommunityByShellRechargeUkOcpiRealtimeDataSource,
    EsbUkOcpiDataSource,
    EsbUkOcpiRealtimeDataSource,
    InstavoltUkOcpiDataSource,
    IonityUkOcpiDataSource,
    IonityUkOcpiRealtimeDataSource,
    MfgUkOcpiDataSource,
    NdwNetherlandsOcpiDataSource,
    ShellRechargeUkOcpiDataSource,
    ShellRechargeUkOcpiRealtimeDataSource,
    TeslaUkOcpiDataSource,
)
from evmap_backend.data_sources.opendata_swiss.source import (
    OpendataSwissDataSource,
    OpendataSwissRealtimeDataSource,
)

DATA_SOURCE_CLASSES: List[Type[DataSource]] = [
    # multiple countries
    GoingElectricDataSource,
    # Austria
    Datex2AustriaDataSource,
    Datex2AustriaRealtimeDataSource,
    # Germany
    # MontaDataSource, # replaced by Mobilithek-Monta
    # ElisoDataSource,  # Eliso is already included in the Eco-Movement data
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
    Datex2MobilithekTeslaDataSource,
    Datex2MobilithekTeslaRealtimeDataSource,
    Datex2MobilithekSmatricsDataSource,
    Datex2MobilithekSmatricsRealtimeDataSource,
    # Datex2MobilithekEroundDataSource,  # no data uploaded yet
    # Datex2MobilithekEroundRealtimeDataSource,  # no data uploaded yet
    Datex2MobilithekMontaDataSource,  # no data uploaded yet
    Datex2MobilithekMontaRealtimeDataSource,  # no data uploaded yet
    # Datex2MobilithekGridAndCoDataSource,  # no data uploaded yet
    # Datex2MobilithekGridAndCoRealtimeDataSource,  # no data uploaded yet
    # Datex2MobilithekEnioDataSource,  # no data uploaded yet
    Datex2MobilithekPumpDataSource,
    Datex2MobilithekM8MitDataSource,
    Datex2MobilithekM8MitRealtimeDataSource,
    # Datex2MobilithekEluMobilityDataSource,  # data not valid (missing coordinates)
    # Datex2MobilithekEluMobilityRealtimeDataSource,  # no data uploaded yet
    # Datex2MobilithekQwelloDataSource,  # no data uploaded yet
    # Datex2MobilithekQwelloRealtimeDataSource,  # no data uploaded yet
    # Datex2MobilithekEonDriveDataSource,  # no data uploaded yet
    # Datex2MobilithekEonDriveRealtimeDataSource,  # no data uploaded yet
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
    ShellRechargeUkOcpiDataSource,
    ShellRechargeUkOcpiRealtimeDataSource,
    CommunityByShellRechargeUkOcpiDataSource,
    CommunityByShellRechargeUkOcpiRealtimeDataSource,
    ChargyUkOcpiDataSource,
    MfgUkOcpiDataSource,
    TeslaUkOcpiDataSource,
    InstavoltUkOcpiDataSource,
    # Latvia
    # LatviaOcpiDataSource,  # Data is malformed (duplicate IDs)
    # Slovenia
    Datex2SloveniaDataSource,
    Datex2SloveniaRealtimeDataSource,
    # Denmark
    Datex2DenmarkEcoMovementDataSource,
    # Belgium
    Datex2BelgiumEcoMovementDataSource,
    # Switzerland
    OpendataSwissDataSource,
    OpendataSwissRealtimeDataSource,
]
DATA_SOURCE_REGISTRY: Dict[str, Type[DataSource]] = {
    cls.id: cls for cls in DATA_SOURCE_CLASSES
}


def setup_data_sources():
    """Perform initialization needed for all data sources"""
    for source_id, source_class in DATA_SOURCE_REGISTRY.items():
        source_class().setup()


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
