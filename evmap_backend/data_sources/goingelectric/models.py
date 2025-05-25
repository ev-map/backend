from django.contrib.gis.db.models import PointField
from django.db import models


class GoingElectricChargeLocation(models.Model):
    """
    Only includes fields available from chargepoint list API (chargepoint detail API has more details)
    """

    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255, blank=True)
    coordinates = PointField(srid=4326)
    address_city = models.CharField(max_length=255, blank=True)
    address_country = models.CharField(max_length=255, blank=True)
    address_postcode = models.CharField(max_length=255, blank=True)
    address_street = models.CharField(max_length=255, blank=True)
    network = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=255)
    fault_report = models.BooleanField()
    verified = models.BooleanField()


class GoingElectricChargepoint(models.Model):
    chargelocation = models.ForeignKey(
        GoingElectricChargeLocation, on_delete=models.CASCADE
    )
    type = models.CharField(max_length=255)
    power = models.FloatField()
    count = models.IntegerField()
