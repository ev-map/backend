from django.conf import settings
from django.db import connection
from ninja.errors import HttpError
from ninja.security import django_auth

from evmap_backend.api import api
from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.chargers.fields import format_evseid
from evmap_backend.chargers.models import ChargingSite
from evmap_backend.helpers.database import blank_to_none, distinct_on
from evmap_backend.realtime.models import RealtimeStatus

from .schemas import (
    ChargepointStatusSchema,
    ConnectorSchema,
    SiteDetailSchema,
)

UTILIZATION_LOOKBACK_WEEKS = 4


def _get_hourly_utilization(site_id: int, tz: str) -> list[list[float]] | None:
    """
    Compute average hourly utilization per day-of-week for a site.
    Returns a 7x24 nested array: result[day][hour], where day 0=Monday .. 6=Sunday.
    Hours and days are in the given timezone.

    Uses a raw PostgreSQL query because:
    - We need generate_series() to create hourly time buckets.
    - For each (chargepoint, bucket) we need the last known status via LATERAL join
      (RealtimeStatus only records changes, so we carry forward the last observation).
    """
    query = """
        WITH chargepoints AS (
            SELECT id FROM chargers_chargepoint WHERE site_id = %s
        ),
        buckets AS (
            SELECT generate_series(
                date_trunc('hour', now() - make_interval(weeks => %s)),
                date_trunc('hour', now()),
                interval '1 hour'
            ) AS bucket
        ),
        grid AS (
            SELECT cp.id AS chargepoint_id, b.bucket
            FROM chargepoints cp CROSS JOIN buckets b
        ),
        filled AS (
            SELECT
                g.chargepoint_id,
                g.bucket,
                ls.status
            FROM grid g
            LEFT JOIN LATERAL (
                SELECT rs.status
                FROM realtime_realtimestatus rs
                WHERE rs.chargepoint_id = g.chargepoint_id
                  AND rs.timestamp <= g.bucket + interval '1 hour'
                ORDER BY rs.timestamp DESC
                LIMIT 1
            ) ls ON TRUE
        )
        SELECT
            EXTRACT(ISODOW FROM bucket AT TIME ZONE %s)::int AS day_of_week,
            EXTRACT(HOUR FROM bucket AT TIME ZONE %s)::int AS hour,
            AVG(CASE WHEN status IN ('CHARGING', 'BLOCKED', 'RESERVED') THEN 1.0 ELSE 0.0 END) AS utilization
        FROM filled
        WHERE status IS NOT NULL
        GROUP BY day_of_week, hour
        ORDER BY day_of_week, hour;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, [site_id, UTILIZATION_LOOKBACK_WEEKS, tz, tz])
        rows = cursor.fetchall()

    if not rows:
        return None

    # Build 7x24 nested array (Monday=0 .. Sunday=6)
    result = [[0.0] * 24 for _ in range(7)]
    for dow, hour, util in rows:
        result[dow - 1][hour] = round(util, 4)  # ISODOW is 1-based

    return result


@api.get(
    "/sites/{site_id}", response=SiteDetailSchema, auth=[django_auth, ApiKeyAuth()]
)
def site_detail(request, site_id: int, tz: str = None):
    if tz is None:
        tz = settings.TIME_ZONE
    try:
        site = (
            ChargingSite.objects.select_related("network")
            .prefetch_related("chargepoints__connectors")
            .get(pk=site_id)
        )
    except ChargingSite.DoesNotExist:
        raise HttpError(404, "Site not found")

    # Get latest realtime status per chargepoint
    chargepoint_ids = [cp.id for cp in site.chargepoints.all()]
    latest_statuses = {}
    if chargepoint_ids:
        qs = RealtimeStatus.objects.filter(chargepoint_id__in=chargepoint_ids)
        for rs in distinct_on(qs, ["chargepoint"], "timestamp"):
            latest_statuses[rs.chargepoint_id] = rs

    # Build chargepoint list
    chargepoints = []
    for cp in site.chargepoints.all():
        rs = latest_statuses.get(cp.id)
        chargepoints.append(
            ChargepointStatusSchema(
                evseid=blank_to_none(format_evseid(cp.evseid)),
                physical_reference=blank_to_none(cp.physical_reference),
                connectors=[
                    ConnectorSchema(
                        connector_type=con.connector_type,
                        connector_format=blank_to_none(con.connector_format),
                        max_power=con.max_power / 1000,
                    )
                    for con in cp.connectors.all()
                ],
                status=rs.status if rs else None,
                status_timestamp=rs.timestamp.isoformat() if rs else None,
            )
        )

    # Compute utilization
    utilization = _get_hourly_utilization(site.id, tz)

    return SiteDetailSchema(
        id=site.id,
        name=site.name,
        location=(site.location.x, site.location.y),
        street=blank_to_none(site.street),
        zipcode=blank_to_none(site.zipcode),
        city=blank_to_none(site.city),
        country=str(site.country),
        network=site.network.name if site.network else None,
        operator=blank_to_none(site.operator),
        opening_hours=blank_to_none(site.opening_hours),
        data_source=site.data_source,
        chargepoints=chargepoints,
        utilization=utilization,
    )
