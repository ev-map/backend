from django.contrib.gis.db.models import PointField
from django.db import models


# Create your models here.
class ChargeLocation(models.Model):
    name = models.CharField(max_length=255, blank=True)
    position = PointField(srid=4326)
    network = models.CharField(max_length=255, blank=True)


class EVSE(models.Model):
    chargelocation = models.ForeignKey(ChargeLocation, on_delete=models.CASCADE)
    evse_id = models.CharField(max_length=255, blank=True)


class Connector(models.Model):
    class Type(models.TextChoices):
        TYPE_1 = "type1", "Type 1"
        TYPE_2_SOCKET = "type2_socket", "Type 2 (socket)"
        TYPE_2_PLUG = "type2_plug", "Type 2 (plug)"
        TYPE_3A = "type3a", "Type 3A"
        TYPE_3C = "type3c", "Type 3C"
        GBT_AC = "gbt_ac", "GB/T AC"

        SCHUKO = "schuko", "Schuko"
        CEE_BLUE = "cee_blue", "CEE Blue"
        CEE_RED = "cee_red", "CEE Red"

        CCS_TYPE_1 = "ccs1", "CCS Type 1"
        CCS_TYPE_2 = "ccs2", "CCS Type 2"
        CHADEMO = "chademo", "CHAdeMO"
        GBT_DC = "gbt_dc", "GB/T DC"

        TESLA_DC_EUROPE = (
            "tesla_dc_europe",
            "Tesla Supercharger Europe (DC through Type 2)",
        )
        TESLA_ROADSTER = "tesla_roadster", "Tesla Roadster HPC"
        NACS = "nacs", "NACS"

        OTHER = "other"

    evse = models.ForeignKey(EVSE, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=Type)
    power = models.FloatField()
