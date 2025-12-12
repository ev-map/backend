from django.contrib.gis.db import models
from django_countries.fields import CountryField

from evmap_backend.chargers.fields import EVSEIDField, EVSEIDType, OpeningHoursField
from evmap_backend.chargers.models import Chargepoint


class RealtimeStatus(models.Model):
    class Status(models.TextChoices):
        """
        EVSE status, as defined in OCPI
        """

        AVAILABLE = "AVAILABLE", "Available"
        """Evse is able to start a new charging session"""
        BLOCKED = "BLOCKED", "Blocked"
        """Evse is not accessible because of a physical barrier, i.e. a car"""
        CHARGING = "CHARGING", "Charging"
        """EVSE is in use"""
        INOPERATIVE = "INOPERATIVE", "Inoperative"
        """EVSE is not yet active or it is no longer available (deleted)"""
        OUTOFORDER = "OUTOFORDER", "Out of order"
        """EVSE is currently out of order"""
        PLANNED = "PLANNED", "Planned"
        """EVSE is planned, will be operating soon"""
        REMOVED = "REMOVED", "Removed"
        """EVSE is discontinued/removed."""
        RESERVED = "RESERVED", "Reserved"
        """EVSE is reserved for a particular EV driver and is unavailable for other drivers"""
        UNKNOWN = "UNKNOWN", "Unknown"
        """No status information available. (Also used when offline)"""

    chargepoint = models.ForeignKey(Chargepoint, models.CASCADE)
    status = models.CharField(max_length=20, choices=Status)
    timestamp = models.DateTimeField(auto_now=True)
    data_source = models.CharField(max_length=255)
