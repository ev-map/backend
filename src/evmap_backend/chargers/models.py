from typing import Dict, Tuple

from django.contrib.gis.db import models
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import GeometryType, Transform
from django.db.models.functions import Cast
from django_countries.fields import CountryField

from evmap_backend.chargers.fields import (
    EVSEIDField,
    EVSEIDType,
    EVSEOperatorIDField,
    OpeningHoursField,
    format_evse_operator_id,
    format_evseid,
)


class Network(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["evse_operator_id"]),
        ]

    name = models.CharField(max_length=255, blank=True)
    evse_operator_id = EVSEOperatorIDField(blank=True, unique=True)
    website = models.URLField(blank=True)
    _network_cache = {}

    def __str__(self):
        if self.evse_operator_id:
            return (
                f"{self.name} ({format_evse_operator_id(self.evse_operator_id)})"
                if self.name
                else format_evse_operator_id(self.evse_operator_id)
            )
        else:
            return self.name

    @classmethod
    def get_or_create(
        cls, evse_operator_id: str, defaults: Dict[str, object]
    ) -> Tuple["Network", bool]:
        if evse_operator_id in cls._network_cache:
            return cls._network_cache[evse_operator_id], False

        network, created = Network.objects.get_or_create(
            evse_operator_id=evse_operator_id,
            defaults=defaults,
        )

        cls._network_cache[evse_operator_id] = network

        return network, created


class ChargingSite(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["data_source", "id_from_source"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "id_from_source"],
                name="unique_site_per_source",
            ),
        ]

    data_source = models.CharField(max_length=255)
    id_from_source = models.CharField(max_length=255)
    name = models.TextField()
    location = models.PointField(geography=True)
    location_mercator = models.GeneratedField(
        expression=Transform(Cast("location", GeometryField(srid=4326)), 3857),
        output_field=models.PointField(srid=3857),
        db_persist=True,
    )

    site_evseid = EVSEIDField(evseid_type=EVSEIDType.STATION, blank=True)

    # address
    street = models.TextField(blank=True)
    zipcode = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country = CountryField()

    network = models.ForeignKey(
        Network, on_delete=models.SET_NULL, null=True, related_name="chargingsites"
    )
    operator = models.TextField(blank=True)

    opening_hours = OpeningHoursField(blank=True)

    license_attribution = models.TextField(blank=True)
    license_attribution_link = models.URLField(blank=True)


class Chargepoint(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["site", "id_from_source"]),
            models.Index(fields=["site", "evseid"]),
            models.Index(fields=["evseid"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "id_from_source"],
                name="unique_chargepoint_per_site",
            ),
        ]

    site = models.ForeignKey(
        ChargingSite, on_delete=models.CASCADE, related_name="chargepoints"
    )
    id_from_source = models.CharField(max_length=255)
    evseid = EVSEIDField(evseid_type=EVSEIDType.EVSE, blank=True)
    physical_reference = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return (
            f"Chargepoint {format_evseid(self.evseid)}"
            if self.evseid
            else f"Chargepoint {self.id_from_source}"
        )


class Connector(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["chargepoint", "id_from_source"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["chargepoint", "id_from_source"],
                name="unique_connector_per_chargepoint",
                nulls_distinct=True,
            ),
        ]

    class ConnectorTypes(models.TextChoices):
        TYPE_1 = "Type 1", "Type 1"
        CCS_TYPE_1 = "CCS Type 1", "CCS Type 1"
        TYPE_2 = "Type 2", "Type 2"
        CCS_TYPE_2 = "CCS Type 2", "CCS Type 2"
        TYPE_3A = "Type 3A", "Type 3A"
        TYPE_3C = "Type 3C", "Type 3C"
        CHADEMO = "CHAdeMO", "CHAdeMO"
        MCS = "MCS", "MCS"

        SCHUKO = "Schuko", "Schuko (Type F)"
        DOMESTIC_J = "Domestic J", "Domestic (Type J - Switzerland Type 13)"
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
    id_from_source = models.CharField(
        max_length=255, blank=True, null=True, default=None
    )
    connector_type = models.CharField(max_length=255, choices=ConnectorTypes)
    connector_format = models.CharField(
        max_length=255, choices=ConnectorFormats, blank=True
    )
    max_power = models.FloatField()  # in watts
    is_dc = models.BooleanField(null=True, blank=True, default=None)


def infer_is_dc(connector_type: str) -> bool | None:
    """Infer whether a connector type is DC based on the connector type.

    Returns True for DC, False for AC, None for ambiguous/unknown.
    """
    dc_types = {
        Connector.ConnectorTypes.CCS_TYPE_1,
        Connector.ConnectorTypes.CCS_TYPE_2,
        Connector.ConnectorTypes.CHADEMO,
        Connector.ConnectorTypes.MCS,
        Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
    }
    ac_types = {
        Connector.ConnectorTypes.TYPE_1,
        Connector.ConnectorTypes.TYPE_2,
        Connector.ConnectorTypes.TYPE_3A,
        Connector.ConnectorTypes.TYPE_3C,
        Connector.ConnectorTypes.SCHUKO,
        Connector.ConnectorTypes.DOMESTIC_J,
        Connector.ConnectorTypes.CEE_SINGLE_16,
        Connector.ConnectorTypes.CEE_THREE_16,
        Connector.ConnectorTypes.CEE_THREE_32,
        Connector.ConnectorTypes.CEE_THREE_64,
    }
    if connector_type in dc_types:
        return True
    if connector_type in ac_types:
        return False
    return None
