from typing import Optional, Tuple

from django.db.models import Max
from ninja import Schema

from evmap_backend.chargers.models import ChargingSite


class ChargingSiteSchema(Schema):
    id: int
    network: Optional[str]
    location: Tuple[float, float]
    name: Optional[str]
    operator: Optional[str]
    max_power: float
    data_source: str

    @classmethod
    def build(cls, obj: ChargingSite):
        return cls(
            id=obj.id,
            network=obj.network.name if obj.network else None,
            location=(obj.location.x, obj.location.y),
            name=obj.name,
            operator=obj.operator,
            max_power=obj.chargepoints.aggregate(
                max_power=Max("connectors__max_power")
            )["max_power"]
            or 0,
            data_source=obj.data_source,
        )


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
