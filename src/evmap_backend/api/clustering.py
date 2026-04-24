import math

from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import Centroid, SnapToGrid, Transform
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Polygon
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Case, Count, Max, OuterRef, QuerySet, Subquery, When

from evmap_backend.chargers.models import ChargingSite, Connector
from evmap_backend.helpers.geo import MERCATOR, WGS84

from .schemas import ClusterSchema


def _snap_lo(v: float, grid_size: float) -> float:
    return (math.floor((v + grid_size / 2) / grid_size) - 0.5) * grid_size


def _snap_hi(v: float, grid_size: float) -> float:
    return (math.ceil((v - grid_size / 2) / grid_size) + 0.5) * grid_size


def snap_bbox_to_grid(bbox: Polygon, grid_size: float) -> Polygon:
    """
    Transform a WGS84 bounding box to Web Mercator and expand it to align
    with cell edges of clustering grid (offset by half a grid_size from grid centers).
    """
    bbox.srid = WGS84
    bbox.transform(CoordTransform(SpatialReference(WGS84), SpatialReference(MERCATOR)))

    min_x, min_y, max_x, max_y = bbox.extent
    result = Polygon.from_bbox(
        (
            _snap_lo(min_x, grid_size),
            _snap_lo(min_y, grid_size),
            _snap_hi(max_x, grid_size),
            _snap_hi(max_y, grid_size),
        )
    )
    result.srid = MERCATOR
    return result


def cluster_sites(
    queryset: QuerySet, cluster_radius: float
) -> tuple[list[ClusterSchema], QuerySet]:
    """
    Cluster a queryset of ChargingSites using SnapToGrid in Web Mercator space.

    Returns a tuple of (clusters, singles) where clusters is a list of
    ClusterSchema instances and singles is a queryset of sites that are alone in
    their grid cell.
    """
    snapped = queryset.annotate(
        snapped=SnapToGrid("location_mercator", cluster_radius),
        site_max_power=Subquery(
            Connector.objects.filter(chargepoint__site=OuterRef("pk"))
            .order_by("-max_power")
            .values("max_power")[:1]
        ),
    )
    groups = list(
        snapped.values("snapped").annotate(
            count=Count("id", distinct=True),
            center=Transform(Centroid(Collect("location_mercator")), WGS84),
            ids=Case(When(count__gt=10, then=None), default=ArrayAgg("id")),
            max_power=Max("site_max_power"),
        )
    )

    clusters = []
    single_ids = []
    for g in groups:
        if g["count"] > 1:
            clusters.append(ClusterSchema.model_validate(g))
        else:
            single_ids.append(g["ids"][0])

    singles = ChargingSite.objects.filter(id__in=single_ids)
    return clusters, singles
