from typing import List, Tuple

from django.contrib.gis.geos import Polygon
from ninja import ModelSchema, NinjaAPI
from ninja.orm import register_field

from evmap_backend.chargers.models import ChargingSite

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
