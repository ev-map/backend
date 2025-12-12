import datetime as dt
from typing import List

import django.http
from ninja import NinjaAPI, Schema

from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.chargers.models import ChargingSite
from evmap_backend.helpers.database import distinct_on
from evmap_backend.realtime.models import RealtimeStatus

api = NinjaAPI(urls_namespace="nobil", auth=ApiKeyAuth())


class RealtimeStatusSchema(Schema):
    evseUid: str
    timestamp: dt.datetime
    status: RealtimeStatus.Status


@api.get("/realtime/{nobil_id}", response=List[RealtimeStatusSchema])
def realtime(request, nobil_id: str):
    nobil_id_without_country = str(int(nobil_id.split("_")[1]))
    try:
        charging_site = ChargingSite.objects.get(
            data_source="nobil", id_from_source=nobil_id_without_country
        )
    except ChargingSite.DoesNotExist:
        raise django.http.Http404
    latest_data_per_evse = distinct_on(
        RealtimeStatus.objects.filter(chargepoint__site=charging_site),
        ["chargepoint"],
        "timestamp",
    )
    return [
        {
            "evseUid": data.chargepoint.id_from_source,
            "timestamp": data.timestamp,
            "status": RealtimeStatus.Status(data.status).name,
        }
        for data in latest_data_per_evse
    ]
