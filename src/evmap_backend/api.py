import gzip
import logging
import math
from datetime import timedelta
from typing import List, Optional, Tuple

from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import Centroid, SnapToGrid, Transform
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Polygon
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Max
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.orm import register_field
from ninja.security import django_auth

from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.chargers.fields import format_evseid
from evmap_backend.chargers.models import ChargingSite
from evmap_backend.data_sources import UpdateMethod
from evmap_backend.data_sources.goingelectric.models import GoingElectricChargeLocation
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.registry import get_data_source
from evmap_backend.helpers.database import distinct_on
from evmap_backend.realtime.models import RealtimeStatus

api = NinjaAPI(urls_namespace="evmap")

register_field("PointField", Tuple[float, float])


class ChargingSiteSchema(Schema):
    id: int
    network: Optional[str]
    location: Tuple[float, float]
    name: Optional[str]
    operator: Optional[str]
    max_power: int
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
    ids: List[int]
    max_power: int


class ChargingSitesSchema(Schema):
    sites: List[ChargingSiteSchema]
    clusters: Optional[List[ClusterSchema]]


class RealtimeStatusSchema(Schema):
    evseid: str
    physical_reference: Optional[str]
    status: str
    power: float
    connector: str


class RealtimeStatusesSchema(Schema):
    statuses: List[RealtimeStatusSchema]


@api.get("/sites", response=ChargingSitesSchema, auth=[django_auth, ApiKeyAuth()])
def sites(
    request,
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    cluster: bool = False,
    cluster_radius: float = None,
):
    if cluster:
        # Transform bbox to Web Mercator and expand to align with clustering grid
        region = Polygon.from_bbox((sw_lng, sw_lat, ne_lng, ne_lat))
        region.srid = 4326
        region.transform(CoordTransform(SpatialReference(4326), SpatialReference(3857)))

        # Expand bbox to grid cell edges (half-radius offset from grid centers)
        half = cluster_radius / 2

        def snap_lo(v):
            return (math.floor((v + half) / cluster_radius) - 0.5) * cluster_radius

        def snap_hi(v):
            return (math.ceil((v - half) / cluster_radius) + 0.5) * cluster_radius

        min_x, min_y, max_x, max_y = region.extent
        region = Polygon.from_bbox(
            (
                snap_lo(min_x),
                snap_lo(min_y),
                snap_hi(max_x),
                snap_hi(max_y),
            )
        )
        region.srid = 3857

        queryset = ChargingSite.objects.filter(location_mercator__coveredby=region)

        snapped = queryset.annotate(
            snapped=SnapToGrid("location_mercator", cluster_radius)
        )
        groups = list(
            snapped.values("snapped").annotate(
                count=Count("id", distinct=True),
                center=Transform(Centroid(Collect("location_mercator")), 4326),
                ids=ArrayAgg("id"),
                max_power=Max("chargepoints__connectors__max_power"),
            )
        )

        clusters = []
        single_ids = []
        for g in groups:
            if g["count"] > 1:
                clusters.append(g)
            else:
                single_ids.append(g["ids"][0])

        queryset = ChargingSite.objects.filter(id__in=single_ids).select_related(
            "network"
        )
    else:
        region = Polygon.from_bbox((sw_lng, sw_lat, ne_lng, ne_lat))
        queryset = ChargingSite.objects.filter(location__coveredby=region)
        clusters = None
    return ChargingSitesSchema(
        clusters=clusters,
        sites=[ChargingSiteSchema.build(obj) for obj in queryset[:1000]],
    )


@api.get(
    "/ge_realtime", response=RealtimeStatusesSchema, auth=[django_auth, ApiKeyAuth()]
)
def ge_realtime(request, ge_id: int):
    try:
        ge_site = GoingElectricChargeLocation.objects.get(id=ge_id)
    except GoingElectricChargeLocation.DoesNotExist:
        raise HttpError(404, "GE location not found")

    matched_site = ge_site.matched_site
    if matched_site is None:
        raise HttpError(404, "No matched site for this GE location")

    status = RealtimeStatus.objects.filter(
        chargepoint__in=matched_site.chargepoints.values_list("id")
    )
    latest_status = distinct_on(status, ["chargepoint"], "timestamp")

    if latest_status.count() == 0:
        raise HttpError(404, "No realtime status available for this site")

    statuses = []
    for cp in matched_site.chargepoints.all():
        for con in cp.connectors.all():
            try:
                status = latest_status.get(chargepoint_id=cp.id).status
            except RealtimeStatus.DoesNotExist:
                status = RealtimeStatus.Status.UNKNOWN
            statuses.append(
                RealtimeStatusSchema(
                    evseid=format_evseid(cp.evseid),
                    power=con.max_power / 1000,
                    connector=con.connector_type,
                    physical_reference=cp.physical_reference,
                    status=status,
                )
            )

    return RealtimeStatusesSchema(statuses=statuses)


@api.post("/push/{data_source}")
def push(request, data_source: str):
    """
    HTTP push endpoint for data updates
    """
    data_source = get_data_source(data_source)
    if UpdateMethod.HTTP_PUSH not in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    logging.info(f"Processing push for {data_source.id}...")

    body = request.body
    if request.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)

    data_source.process_push(body)

    update_state, created = UpdateState.objects.get_or_create(
        data_source=data_source.id,
        defaults=dict(last_update=timezone.now(), push=True),
    )
    if timezone.now() - update_state.last_update > timedelta(minutes=1):
        update_state.last_update = timezone.now()
        update_state.push = True
        update_state.save()
    logging.info(f"Successfully processed push for {data_source.id}")

    return 200, ""


@api.api_operation(["HEAD"], "/push/{data_source}")
def push_head(request, data_source: str):
    """
    required by Mobilithek to verify push endpoint
    """
    data_source = get_data_source(data_source)
    if UpdateMethod.HTTP_PUSH not in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    return 200, ""
