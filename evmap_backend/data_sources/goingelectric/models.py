from django.contrib.gis.db.models import PointField
from django.db import models

from evmap_backend.aggregator.models import ChargeLocation, Connector


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
    aggregated_location = models.ForeignKey(
        ChargeLocation,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="source_goingelectric",
    )


class GoingElectricChargepoint(models.Model):
    chargelocation = models.ForeignKey(
        GoingElectricChargeLocation,
        on_delete=models.CASCADE,
        related_name="chargepoints",
    )
    type = models.CharField(max_length=255)
    power = models.FloatField()
    count = models.IntegerField()

    def map_connector_type(self) -> Connector.Type:
        match self.type:
            case "cee_blue":
                return Connector.Type.CEE_BLUE
            case "cee_red":
                return Connector.Type.CEE_RED
            case "ceeplus_red":
                return Connector.Type.CEE_RED
            case "chademo":
                return Connector.Type.CHADEMO
            case "combo_typ1":
                return Connector.Type.CCS_TYPE_1
            case "combo_typ2":
                return Connector.Type.CCS_TYPE_2
            case "gbt":
                # GB/T has different plugs for AC and DC, but GoingElectric does not specify this
                if self.power >= 28:
                    return Connector.Type.GBT_DC
                else:
                    return Connector.Type.GBT_AC
            case "schuko":
                return Connector.Type.SCHUKO
            case "tesla_roadster_hpc":
                return Connector.Type.TESLA_ROADSTER
            case "tesla_supercharger_ccs":
                return Connector.Type.CCS_TYPE_2
            case "tesla_supercharger_eu":
                return Connector.Type.TESLA_DC_EUROPE
            case "tesla_supercharger_us":
                return Connector.Type.NACS
            case "typ2_plug":
                return Connector.Type.TYPE_2_PLUG
            case "typ2_socket":
                return Connector.Type.TYPE_2_SOCKET
            case "typ2_tesla":
                return Connector.Type.TYPE_2_PLUG  # Tesla Destination Charger
            case "typ_1":
                return Connector.Type.TYPE_1
            case "typ_3a":
                return Connector.Type.TYPE_3A
            case "typ_3c":
                return Connector.Type.TYPE_3C
            case _:
                return Connector.Type.OTHER
