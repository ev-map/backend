from typing import Dict, List, Type

from evmap_backend.data_sources import DataSource
from evmap_backend.data_sources.datex2.source import (
    Datex2AudiChargingHubDataSource,
    Datex2AudiChargingHubRealtimeDataSource,
    Datex2AustriaDataSource,
    Datex2AustriaRealtimeDataSource,
    Datex2BelgiumEcoMovementDataSource,
    Datex2DenmarkEcoMovementDataSource,
    Datex2FinlandDataSource,
    Datex2LuxembourgEcoMovementDataSource,
    Datex2MobilithekChargecloudDataSource,
    Datex2MobilithekChargecloudRealtimeDataSource,
    Datex2MobilithekEcoMovementDatex2DataSource,
    Datex2MobilithekEcoMovementRealtimeDataSource,
    Datex2MobilithekEnbwDataSource,
    Datex2MobilithekEnbwRealtimeDataSource,
    Datex2MobilithekEonDriveDataSource,
    Datex2MobilithekEonDriveRealtimeDataSource,
    Datex2MobilithekEroundDataSource,
    Datex2MobilithekEroundRealtimeDataSource,
    Datex2MobilithekEulektroDataSource,
    Datex2MobilithekEulektroRealtimeDataSource,
    Datex2MobilithekGlsMobilityDataSource,
    Datex2MobilithekGlsMobilityRealtimeDataSource,
    Datex2MobilithekGridAndCoDataSource,
    Datex2MobilithekGridAndCoRealtimeDataSource,
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
    Datex2MobilithekVaylensDataSource,
    Datex2MobilithekVaylensRealtimeDataSource,
    Datex2MobilithekWirelaneDataSource,
    Datex2MobilithekWirelaneRealtimeDataSource,
    Datex2SloveniaDataSource,
    Datex2SloveniaRealtimeDataSource,
    Datex2SpainDataSource,
)
from evmap_backend.data_sources.fintraffic.source import FintrafficRealtimeDataSource
from evmap_backend.data_sources.goingelectric.source import GoingElectricDataSource
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
    ClenergyUkOcpiDataSource,
    CommunityByShellRechargeUkOcpiDataSource,
    CommunityByShellRechargeUkOcpiRealtimeDataSource,
    EsbUkOcpiDataSource,
    EsbUkOcpiRealtimeDataSource,
    EvyeUkOcpiDataSource,
    EvyeUkOcpiRealtimeDataSource,
    GeniepointUkOcpiDataSource,
    GoZeroUkOcpiDataSource,
    InstavoltUkOcpiDataSource,
    IonityUkOcpiDataSource,
    IonityUkOcpiRealtimeDataSource,
    MfgUkOcpiDataSource,
    NdwNetherlandsOcpiDataSource,
    RoadBelgiumOcpiDataSource,
    ShellRechargeUkOcpiDataSource,
    ShellRechargeUkOcpiRealtimeDataSource,
    SourceEvUkOcpiDataSource,
    SourceEvUkOcpiRealtimeDataSource,
    TeslaBelgiumOcpiDataSource,
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
    Datex2MobilithekChargecloudDataSource,
    Datex2MobilithekChargecloudRealtimeDataSource,
    Datex2MobilithekEulektroDataSource,
    Datex2MobilithekEulektroRealtimeDataSource,
    Datex2MobilithekEroundDataSource,
    Datex2MobilithekEroundRealtimeDataSource,
    Datex2MobilithekMontaDataSource,
    Datex2MobilithekMontaRealtimeDataSource,
    Datex2MobilithekGridAndCoDataSource,
    Datex2MobilithekGridAndCoRealtimeDataSource,
    # Datex2MobilithekEnioDataSource,  # no data uploaded yet
    Datex2MobilithekPumpDataSource,
    Datex2MobilithekM8MitDataSource,
    Datex2MobilithekM8MitRealtimeDataSource,
    Datex2MobilithekVaylensDataSource,
    Datex2MobilithekVaylensRealtimeDataSource,
    # Datex2MobilithekEluMobilityDataSource,  # data not valid (missing coordinates)
    # Datex2MobilithekEluMobilityRealtimeDataSource,  # no data uploaded yet
    Datex2MobilithekQwelloDataSource,
    Datex2MobilithekQwelloRealtimeDataSource,
    Datex2MobilithekEonDriveDataSource,
    Datex2MobilithekEonDriveRealtimeDataSource,
    Datex2MobilithekGlsMobilityDataSource,
    Datex2MobilithekGlsMobilityRealtimeDataSource,
    Datex2AudiChargingHubDataSource,
    Datex2AudiChargingHubRealtimeDataSource,
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
    GeniepointUkOcpiDataSource,
    ClenergyUkOcpiDataSource,
    GoZeroUkOcpiDataSource,
    EvyeUkOcpiDataSource,
    EvyeUkOcpiRealtimeDataSource,
    SourceEvUkOcpiDataSource,
    SourceEvUkOcpiRealtimeDataSource,
    # Latvia
    # LatviaOcpiDataSource,  # Data is malformed (duplicate IDs)
    # Slovenia
    Datex2SloveniaDataSource,
    Datex2SloveniaRealtimeDataSource,
    # Denmark
    Datex2DenmarkEcoMovementDataSource,
    # Belgium
    Datex2BelgiumEcoMovementDataSource,
    RoadBelgiumOcpiDataSource,
    TeslaBelgiumOcpiDataSource,
    # Switzerland
    OpendataSwissDataSource,
    OpendataSwissRealtimeDataSource,
    # Finland
    Datex2FinlandDataSource,
    FintrafficRealtimeDataSource,
    # Spain
    Datex2SpainDataSource,
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
