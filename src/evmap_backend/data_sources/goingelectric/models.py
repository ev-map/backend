from django.contrib.gis.db.models import PointField
from django.db import models


class GoingElectricNetwork(models.Model):
    name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


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
    network = models.ForeignKey(
        GoingElectricNetwork,
        on_delete=models.SET_NULL,
        null=True,
        related_name="chargelocations",
    )
    url = models.URLField(max_length=255)
    fault_report = models.BooleanField()
    verified = models.BooleanField()


class GoingElectricChargepoint(models.Model):
    class ConnectorTypes(models.TextChoices):
        CCS_UNKNOWN = "CCS", "CCS"
        CHADEMO = "CHAdeMO", "CHAdeMO"

        TYPE_1 = "Typ1", "Type 1"
        TYPE_2 = "Typ2", "Type 2"
        TYPE_3 = "Typ3", "Type 3"

        TESLA_SUPERCHARGER_CCS = "Tesla Supercharger CCS", "Tesla Supercharger CCS"
        TESLA_SUPERCHARGER = "Tesla Supercharger", "Tesla Supercharger"
        TESLA_HPC = "Tesla HPC", "Tesla Roadster HPC"

        SCHUKO = "Schuko", "Schuko"
        TYP_13 = "Typ13", "Typ 13"
        TYP_15 = "Typ15", "Typ 15"
        TYP_23 = "Typ23", "Typ 23"
        TYP_25 = "Typ25", "Typ 25"
        CEE_RED = "CEE Rot", "CEE Red"
        CEE_BLUE = "CEE Blau", "CEE Blue"
        CEE_PLUS = "CEE+", "CEE+"

    chargelocation = models.ForeignKey(
        GoingElectricChargeLocation, on_delete=models.CASCADE
    )
    type = models.CharField(max_length=255, choices=ConnectorTypes)
    power = models.FloatField()
    count = models.IntegerField()
