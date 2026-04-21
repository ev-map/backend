from ninja.errors import HttpError
from ninja.security import django_auth

from evmap_backend.api import api
from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.chargers.fields import format_evseid
from evmap_backend.data_sources.goingelectric.models import GoingElectricChargeLocation
from evmap_backend.helpers.database import distinct_on
from evmap_backend.realtime.models import RealtimeStatus

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
