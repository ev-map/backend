import gzip
import logging
from typing import List, Optional, Tuple

from django.contrib.gis.geos import Polygon
from ninja import ModelSchema, NinjaAPI, Schema
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


class ChargingSitesSchema(ModelSchema):
    country: str
    network: Optional[str]

    @staticmethod
    def resolve_country(obj: ChargingSite) -> str:
        return obj.country.code

    @staticmethod
    def resolve_network(obj: ChargingSite) -> str:
        return obj.network.name if obj.network else None

    class Meta:
        model = ChargingSite
        fields = "__all__"


class RealtimeStatusSchema(Schema):
    evseid: str
    physical_reference: Optional[str]
    status: str
    power: float
    connector: str


class RealtimeStatusesSchema(Schema):
    statuses: List[RealtimeStatusSchema]


@api.get("/sites", response=List[ChargingSitesSchema], auth=[django_auth, ApiKeyAuth()])
def sites(request, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float):
    region = Polygon.from_bbox((sw_lng, sw_lat, ne_lng, ne_lat))
    return ChargingSite.objects.filter(location__coveredby=region)[:1000]


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
    if not UpdateMethod.HTTP_PUSH in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    logging.info(f"Processing push for {data_source.id}...")

    body = request.body
    if request.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)

    data_source.process_push(body)

    UpdateState(data_source=data_source.id, push=True).save()
    logging.info(f"Successfully processed push for {data_source.id}")

    return 200, ""


@api.api_operation(["HEAD"], "/push/{data_source}")
def push_head(request, data_source: str):
    """
    required by Mobilithek to verify push endpoint
    """
    data_source = get_data_source(data_source)
    if not UpdateMethod.HTTP_PUSH in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    return 200, ""
