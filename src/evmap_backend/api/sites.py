from django.contrib.gis.geos import Polygon
from ninja.security import django_auth

from evmap_backend.api import api
from evmap_backend.apikeys.ninja import ApiKeyAuth
from evmap_backend.chargers.models import ChargingSite

from .clustering import cluster_sites, snap_bbox_to_grid
from .schemas import ChargingSiteSchema, ChargingSitesSchema


@api.get("/sites", response=ChargingSitesSchema, auth=[django_auth, ApiKeyAuth()])
def sites(
    request,
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    cluster_grid: float = None,
):
    if cluster_grid:
        region = snap_bbox_to_grid(
            Polygon.from_bbox((sw_lng, sw_lat, ne_lng, ne_lat)),
            cluster_grid,
        )
        queryset = ChargingSite.objects.filter(location_mercator__coveredby=region)
        clusters, queryset = cluster_sites(queryset, cluster_grid)
    else:
        region = Polygon.from_bbox((sw_lng, sw_lat, ne_lng, ne_lat))
        queryset = ChargingSite.objects.filter(location__coveredby=region)
        clusters = None
    return ChargingSitesSchema(
        clusters=clusters,
        sites=[ChargingSiteSchema.build(obj) for obj in queryset[:1000]],
    )
