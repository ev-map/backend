import gzip
import logging
from typing import List, Tuple

from django.contrib.gis.geos import Polygon
from ninja import ModelSchema, NinjaAPI
from ninja.orm import register_field

from evmap_backend.chargers.models import ChargingSite
from evmap_backend.data_sources import UpdateMethod
from evmap_backend.data_sources.models import UpdateState
from evmap_backend.data_sources.registry import get_data_source

api = NinjaAPI(urls_namespace="evmap")

register_field("PointField", Tuple[float, float])


class ChargingSitesSchema(ModelSchema):
    country: str

    @staticmethod
    def resolve_country(obj) -> str:
        return obj.country.code

    class Meta:
        model = ChargingSite
        fields = "__all__"


@api.get("/sites", response=List[ChargingSitesSchema])
def sites(request, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float):
    region = Polygon.from_bbox((sw_lng, sw_lat, ne_lng, ne_lat))
    return ChargingSite.objects.filter(location__within=region)[:1000]


@api.post("/push/{data_source}")
def push(request, data_source: str):
    data_source = get_data_source(data_source)
    if not UpdateMethod.HTTP_PUSH in data_source.supported_update_methods:
        raise ValueError("Data source does not support push")

    data_source.verify_push(request)

    logging.info(f"Processing push for {data_source}...")

    body = request.body
    if request.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)

    data_source.process_push(body)

    UpdateState(data_source=data_source.id, push=True).save()
    logging.info(f"Successfully processed push for {data_source}")
