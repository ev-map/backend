from ninja.errors import HttpError
from ninja.security import django_auth

from evmap_backend.api import api
from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.chargers.fields import format_evseid
from evmap_backend.data_sources.goingelectric.models import GoingElectricChargeLocation
from evmap_backend.realtime.models import CurrentStatus

from .schemas import RealtimeStatusesSchema, RealtimeStatusSchema


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

    status_map = {
        status.chargepoint_id: status
        for status in CurrentStatus.objects.filter(
            chargepoint__in=matched_site.chargepoints.values_list("id")
        )
    }

    if not status_map:
        raise HttpError(404, "No realtime status available for this site")

    statuses = []
    for cp in matched_site.chargepoints.all():
        for con in cp.connectors.all():
            status = status_map.get(cp.id)
            statuses.append(
                RealtimeStatusSchema(
                    evseid=format_evseid(cp.evseid),
                    power=con.max_power / 1000,
                    connector=con.connector_type,
                    physical_reference=cp.physical_reference,
                    status=(status.status if status else CurrentStatus.Status.UNKNOWN),
                )
            )

    return RealtimeStatusesSchema(statuses=statuses)
