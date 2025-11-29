from django.contrib.gis.db import models
from django_countries.fields import CountryField

from evmap_backend.chargers.fields import EVSEIDField, EVSEIDType, OpeningHoursField


class ChargingSite(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["data_source", "id_from_source"]),
        ]

    data_source = models.CharField(max_length=255)
    id_from_source = models.CharField(max_length=255)
    name = models.TextField()
    location = models.PointField()

    site_evseid = EVSEIDField(evseid_type=EVSEIDType.STATION, blank=True)

    # address
    street = models.TextField(blank=True)
    zipcode = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country = CountryField()

    network = models.TextField(blank=True)
    operator = models.TextField(blank=True)

    opening_hours = OpeningHoursField(blank=True)


class Chargepoint(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["site", "id_from_source"]),
        ]

    site = models.ForeignKey(
        ChargingSite, on_delete=models.CASCADE, related_name="chargepoints"
    )
    id_from_source = models.CharField(max_length=255, blank=True)
    evseid = EVSEIDField(evseid_type=EVSEIDType.EVSE, blank=True)


class Connector(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["chargepoint", "id_from_source"]),
        ]

    class ConnectorTypes(models.TextChoices):
        TYPE_1 = "Type 1", "Type 1"
        CCS_TYPE_1 = "CCS Type 1", "CCS Type 1"
        TYPE_2 = "Type 2", "Type 2"
        CCS_TYPE_2 = "CCS Type 2", "CCS Type 2"
        TYPE_3A = "Type 3A", "Type 3A"
        TYPE_3C = "Type 3C", "Type 3C"
        CHADEMO = "CHAdeMO", "CHAdeMO"

        SCHUKO = "Schuko", "Schuko (Type F)"
        # TODO: add other household plugs

        NACS = "NACS", "NACS (Tesla US)"
        TESLA_SUPERCHARGER_EU = (
            "Tesla Supercharger EU",
            "Tesla Supercharger EU (Type 2)",
        )
        TESLA_ROADSTER_HPC = "Tesla Roadster HPC", "Tesla Roadster HPC"

        CEE_SINGLE_16 = "iec60309x2single16", "CEE single-phase 16 A"
        CEE_THREE_16 = "iec60309x2three16", "CEE three-phase 16 A"
        CEE_THREE_32 = "iec60309x2three32", "CEE three-phase 32 A"
        CEE_THREE_64 = "iec60309x2three64", "CEE three-phase 63 A"

        OTHER = "other"

    class ConnectorFormats(models.TextChoices):
        SOCKET = "socket", "socket"
        CABLE = "cable", "cable"

    chargepoint = models.ForeignKey(
        Chargepoint, on_delete=models.CASCADE, related_name="connectors"
    )
    id_from_source = models.CharField(max_length=255, blank=True)
    connector_type = models.CharField(max_length=255, choices=ConnectorTypes)
    connector_format = models.CharField(
        max_length=255, choices=ConnectorFormats, blank=True
    )
    max_power = models.FloatField()  # in watts
