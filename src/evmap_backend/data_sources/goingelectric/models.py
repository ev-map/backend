from typing import Dict, Set

from django.contrib.gis.db.models import GeometryField, PointField
from django.contrib.gis.db.models.functions import Transform
from django.db import models
from django.db.models.functions import Cast

from evmap_backend.chargers.models import Connector
from evmap_backend.helpers.geo import MERCATOR, WGS84


class GoingElectricNetwork(models.Model):
    name = models.CharField(max_length=255, blank=True)
    mapped_networks = models.ManyToManyField(
        "chargers.Network",
        blank=True,
        related_name="goingelectric_networks",
    )

    def __str__(self):
        return self.name


class GoingElectricChargeLocation(models.Model):
    """
    Only includes fields available from chargepoint list API (chargepoint detail API has more details)
    """

    id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255, blank=True)
    coordinates = PointField(srid=WGS84, geography=True)
    coordinates_mercator = models.GeneratedField(
        expression=Transform(Cast("coordinates", GeometryField(srid=WGS84)), MERCATOR),
        output_field=PointField(srid=MERCATOR),
        db_persist=True,
    )
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

    matched_site = models.OneToOneField(
        "chargers.ChargingSite",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goingelectric_match",
    )
    match_confidence = models.FloatField(null=True, blank=True)


class GoingElectricChargepoint(models.Model):
    class ConnectorTypes(models.TextChoices):
        CCS = "CCS", "CCS"
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


# Maps GoingElectric connector types to compatible Connector.ConnectorTypes values.
# GE types are coarser, so some map to multiple possibilities.
GE_CONNECTOR_TYPE_MAP: Dict[str, Set[str]] = {
    GoingElectricChargepoint.ConnectorTypes.CCS: {
        Connector.ConnectorTypes.CCS_TYPE_1,
        Connector.ConnectorTypes.CCS_TYPE_2,
    },
    GoingElectricChargepoint.ConnectorTypes.CHADEMO: {
        Connector.ConnectorTypes.CHADEMO,
    },
    GoingElectricChargepoint.ConnectorTypes.TYPE_1: {
        Connector.ConnectorTypes.TYPE_1,
    },
    GoingElectricChargepoint.ConnectorTypes.TYPE_2: {
        Connector.ConnectorTypes.TYPE_2,
    },
    GoingElectricChargepoint.ConnectorTypes.TYPE_3: {
        Connector.ConnectorTypes.TYPE_3A,
        Connector.ConnectorTypes.TYPE_3C,
    },
    GoingElectricChargepoint.ConnectorTypes.TESLA_SUPERCHARGER_CCS: {
        Connector.ConnectorTypes.CCS_TYPE_2,
    },
    GoingElectricChargepoint.ConnectorTypes.TESLA_SUPERCHARGER: {
        Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
    },
    GoingElectricChargepoint.ConnectorTypes.TESLA_HPC: {
        Connector.ConnectorTypes.TESLA_ROADSTER_HPC,
    },
    GoingElectricChargepoint.ConnectorTypes.SCHUKO: {
        Connector.ConnectorTypes.SCHUKO,
    },
    GoingElectricChargepoint.ConnectorTypes.CEE_RED: {
        Connector.ConnectorTypes.CEE_THREE_16,
        Connector.ConnectorTypes.CEE_THREE_32,
        Connector.ConnectorTypes.CEE_THREE_64,
    },
    GoingElectricChargepoint.ConnectorTypes.CEE_BLUE: {
        Connector.ConnectorTypes.CEE_SINGLE_16,
    },
    GoingElectricChargepoint.ConnectorTypes.CEE_PLUS: {
        Connector.ConnectorTypes.CEE_THREE_16,
        Connector.ConnectorTypes.CEE_THREE_32,
        Connector.ConnectorTypes.CEE_THREE_64,
    },
    # Swiss connector types
    GoingElectricChargepoint.ConnectorTypes.TYP_13: {
        Connector.ConnectorTypes.DOMESTIC_J,
    },
    GoingElectricChargepoint.ConnectorTypes.TYP_15: {
        Connector.ConnectorTypes.OTHER,
    },
    GoingElectricChargepoint.ConnectorTypes.TYP_23: {
        Connector.ConnectorTypes.DOMESTIC_J,
    },
    GoingElectricChargepoint.ConnectorTypes.TYP_25: {
        Connector.ConnectorTypes.OTHER,
    },
}
