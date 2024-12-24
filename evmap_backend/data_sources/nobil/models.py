from django.db import models


class NobilRealtimeData(models.Model):
    class Status(models.TextChoices):
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

    nobil_id = models.CharField(max_length=20)
    evse_uid = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        get_latest_by = "timestamp"
        indexes = [
            models.Index(fields=["nobil_id", "evse_uid", "timestamp"]),
        ]
