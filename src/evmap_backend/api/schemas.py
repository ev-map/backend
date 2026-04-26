from typing import List, Optional, Tuple

from django.db.models import Max, QuerySet
from ninja import Schema


class ChargingSiteSchema(Schema):
    id: int
    network: Optional[str]
    location: Tuple[float, float]
    name: Optional[str]
    operator: Optional[str]
    max_power: float
    data_source: str

    @classmethod
    def build_from_queryset(cls, qs: QuerySet) -> List["ChargingSiteSchema"]:
        qs = qs.annotate(
            max_power=Max("chargepoints__connectors__max_power")
        ).select_related("network")
        return [
            cls(
                id=obj.id,
                network=obj.network.name if obj.network else None,
                location=(obj.location.x, obj.location.y),
                name=obj.name,
                operator=obj.operator,
                max_power=obj.max_power or 0,
                data_source=obj.data_source,
            )
            for obj in qs
        ]


class ClusterSchema(Schema):
    center: tuple[float, float]
    count: int
    ids: Optional[list[int]]
    max_power: float


class ChargingSitesSchema(Schema):
    sites: list[ChargingSiteSchema]
    clusters: Optional[list[ClusterSchema]]


class RealtimeStatusSchema(Schema):
    evseid: str
    physical_reference: Optional[str]
    status: str
    power: float
    connector: str


class RealtimeStatusesSchema(Schema):
    statuses: list[RealtimeStatusSchema]


class ConnectorSchema(Schema):
    connector_type: str
    connector_format: Optional[str] = None
    max_power: float  # in kW


class ChargepointStatusSchema(Schema):
    evseid: Optional[str] = None
    physical_reference: Optional[str] = None
    connectors: list[ConnectorSchema]
    status: Optional[str] = None
    status_timestamp: Optional[str] = None


class GoingElectricMatch(Schema):
    id: int
    url: str


class SiteDetailSchema(Schema):
    id: int
    name: str
    location: Tuple[float, float]
    street: Optional[str] = None
    zipcode: Optional[str] = None
    city: Optional[str] = None
    country: str
    network: Optional[str] = None
    operator: Optional[str] = None
    opening_hours: Optional[str] = None
    data_source: str
    goingelectric: Optional[GoingElectricMatch] = None
    chargepoints: list[ChargepointStatusSchema]
    utilization: Optional[list[list[float]]] = None  # 7x24: [day_of_week][hour], Mon=0
