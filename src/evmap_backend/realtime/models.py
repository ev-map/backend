from django.contrib.gis.db import models

from evmap_backend.chargers.models import Chargepoint


class RealtimeStatus(models.Model):
    class Meta:
        abstract = True
        get_latest_by = "timestamp"

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
    timestamp = models.DateTimeField()
    data_source = models.CharField(max_length=255)
    license_attribution = models.TextField(blank=True)
    license_attribution_link = models.URLField(blank=True)

    def __str__(self):
        return f"{self.chargepoint_id}: {self.status} @ {self.timestamp}"


class PreviousStatus(RealtimeStatus):
    class Meta(RealtimeStatus.Meta):
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["chargepoint", "-timestamp"]),
            models.Index(fields=["data_source", "-timestamp"]),
            models.Index(fields=["data_source", "chargepoint", "-timestamp"]),
        ]


class CurrentStatus(RealtimeStatus):
    chargepoint = models.OneToOneField(
        Chargepoint, on_delete=models.CASCADE, related_name="current_status"
    )

    class Meta(RealtimeStatus.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["chargepoint"],
                name="unique_current_status_per_chargepoint",
            )
        ]
        indexes = [
            models.Index(fields=["chargepoint"]),
        ]
