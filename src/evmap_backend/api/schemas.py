from django.db.models import Max, QuerySet
from ninja import Schema


class ChargingSiteSchema(Schema):
    id: int
    network: str | None
    location: tuple[float, float]
    name: str | None
    operator: str | None
    max_power: float
    data_source: str

    @classmethod
    def build_from_queryset(cls, qs: QuerySet) -> list["ChargingSiteSchema"]:
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
    ids: list[int] | None
    max_power: float


class ChargingSitesSchema(Schema):
    sites: list[ChargingSiteSchema]
    clusters: list[ClusterSchema] | None


class RealtimeStatusSchema(Schema):
    evseid: str
    physical_reference: str | None
    status: str
    power: float
    connector: str


class RealtimeStatusesSchema(Schema):
    statuses: list[RealtimeStatusSchema]


class ConnectorSchema(Schema):
    connector_type: str
    connector_format: str | None = None
    max_power: float  # in kW


class ChargepointStatusSchema(Schema):
    evseid: str | None = None
    physical_reference: str | None = None
    connectors: list[ConnectorSchema]
    status: str | None = None
    status_timestamp: str | None = None


class GoingElectricMatch(Schema):
    id: int
    url: str


class SiteDetailSchema(Schema):
    id: int
    name: str
    location: tuple[float, float]
    street: str | None = None
    zipcode: str | None = None
    city: str | None = None
    country: str
    network: str | None = None
    operator: str | None = None
    opening_hours: str | None = None
    data_source: str
    goingelectric: GoingElectricMatch | None = None
    chargepoints: list[ChargepointStatusSchema]
    utilization: list[list[float]] | None = None  # 7x24: [day_of_week][hour], Mon=0
