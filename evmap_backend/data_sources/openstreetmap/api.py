import datetime as dt
from typing import List

from ninja import NinjaAPI, Schema

from evmap_backend.data_sources.openstreetmap.models import OsmNode

api = NinjaAPI(urls_namespace="openstreetmap")


class OsmNodeSchema(Schema):
    id: int
    lat: float
    lon: float
    timestamp: dt.datetime
    version: int
    user: str
    uid: int
    tags: dict


class DumpSchema(Schema):
    count: int
    elements: List[OsmNodeSchema]


@api.get("/dump", response=DumpSchema)
def realtime(request):
    elements = OsmNode.objects.all()
    return {
        "count": elements.count(),
        "elements": [
            {
                "id": elem.id,
                "lat": elem.location.y,
                "lon": elem.location.x,
                "timestamp": elem.timestamp,
                "version": elem.version,
                "user": elem.user,
                "uid": elem.uid,
                "tags": elem.tags,
            }
            for elem in elements
        ],
    }
