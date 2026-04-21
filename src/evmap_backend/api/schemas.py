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
        qs = qs.annotate(max_power=Max("chargepoints__connectors__max_power"))
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
    ids: list[int]
    max_power: int


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
