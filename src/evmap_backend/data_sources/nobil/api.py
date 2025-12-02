import datetime as dt
from typing import List

from ninja import NinjaAPI, Schema

from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.data_sources.nobil.models import NobilRealtimeData
from evmap_backend.helpers.database import distinct_on

api = NinjaAPI(urls_namespace="nobil", auth=ApiKeyAuth())


class RealtimeStatusSchema(Schema):
    evseUid: str
    timestamp: dt.datetime
    status: NobilRealtimeData.Status


@api.get("/realtime/{nobil_id}", response=List[RealtimeStatusSchema])
def realtime(request, nobil_id: str):
    latest_data_per_evse = distinct_on(
        NobilRealtimeData.objects.filter(nobil_id=nobil_id), ["evse_uid"], "timestamp"
    )
    print(latest_data_per_evse.query)
    print(latest_data_per_evse.explain())
    return [
        {
            "evseUid": data.evse_uid,
            "timestamp": data.timestamp,
            "status": NobilRealtimeData.Status(data.status).name,
        }
        for data in latest_data_per_evse
    ]
