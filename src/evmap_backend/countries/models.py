from django.contrib.gis.db import models
from django.contrib.gis.geos import Point


class Country(models.Model):
    iso2 = models.CharField(max_length=2, primary_key=True)
    iso3 = models.CharField(max_length=3)
    name = models.CharField(max_length=255)
    geom = models.MultiPolygonField()

    @staticmethod
    def get_country_for_point(point: Point) -> str | None:
        """Return the ISO2 country code for a point, or None if not found."""
        match = Country.objects.filter(geom__contains=point).first()
        if match is None:
            return None
        return match.iso2
