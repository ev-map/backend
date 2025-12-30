"""
Tests for the sync_statuses bulk operations.
"""

from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from evmap_backend.chargers.models import Chargepoint, ChargingSite
from evmap_backend.realtime.models import RealtimeStatus
from evmap_backend.sync import sync_statuses

STATIC_SOURCE = "test_static_source"
REALTIME_SOURCE = "test_realtime_source"


def make_status(chargepoint_id_from_source, status=None, timestamp=None):
    """Helper function to create RealtimeStatus instances."""
    if status is None:
        status = RealtimeStatus.Status.AVAILABLE
    if timestamp is None:
        timestamp = timezone.now()
    return RealtimeStatus(
        chargepoint=Chargepoint(id_from_source=chargepoint_id_from_source),
        status=status,
        timestamp=timestamp,
    )


def create_site_with_chargepoints(data_source, site_id, chargepoint_ids):
    """Helper function to create a site with chargepoints in the database."""
    site = ChargingSite.objects.create(
        data_source=data_source,
        id_from_source=site_id,
        name=f"Site {site_id}",
        location=Point(10.0, 50.0),
        country="DE",
    )
    for cp_id in chargepoint_ids:
        Chargepoint.objects.create(
            site=site,
            id_from_source=cp_id,
        )
    return site


@pytest.mark.django_db(transaction=True)
class TestSyncStatuses:
    def test_sync_empty_statuses(self):
        """Test syncing with empty status data."""
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [])

        assert RealtimeStatus.objects.count() == 0

    def test_sync_create_single_status(self):
        """Test creating a single status for a chargepoint."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])
        status = make_status("cp_1", RealtimeStatus.Status.AVAILABLE)

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_1", status)])

        assert RealtimeStatus.objects.count() == 1
        saved_status = RealtimeStatus.objects.first()
        assert saved_status.status == RealtimeStatus.Status.AVAILABLE
        assert saved_status.data_source == REALTIME_SOURCE

    def test_sync_create_multiple_statuses(self):
        """Test creating multiple statuses in a single sync."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1", "cp_2", "cp_3"])

        statuses_data = [
            ("site_1", make_status("cp_1", RealtimeStatus.Status.AVAILABLE)),
            ("site_1", make_status("cp_2", RealtimeStatus.Status.CHARGING)),
            ("site_1", make_status("cp_3", RealtimeStatus.Status.OUTOFORDER)),
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 3

    def test_sync_status_newer_timestamp(self):
        """Test that a newer status is created when timestamp is newer."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        old_time = timezone.now() - timedelta(hours=1)
        new_time = timezone.now()

        # Create initial status
        status1 = make_status("cp_1", RealtimeStatus.Status.AVAILABLE, old_time)
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_1", status1)])
        assert RealtimeStatus.objects.count() == 1

        # Create newer status
        status2 = make_status("cp_1", RealtimeStatus.Status.CHARGING, new_time)
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_1", status2)])

        assert RealtimeStatus.objects.count() == 2
        latest_status = RealtimeStatus.objects.latest()
        assert latest_status.status == RealtimeStatus.Status.CHARGING

    def test_sync_status_older_timestamp_ignored(self):
        """Test that an older status is ignored when timestamp is older than existing."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        old_time = timezone.now() - timedelta(hours=1)
        new_time = timezone.now()

        # Create initial status with newer timestamp
        status1 = make_status("cp_1", RealtimeStatus.Status.AVAILABLE, new_time)
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_1", status1)])
        assert RealtimeStatus.objects.count() == 1

        # Try to create older status - should be ignored
        status2 = make_status("cp_1", RealtimeStatus.Status.CHARGING, old_time)
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_1", status2)])

        # Should still be 1 status
        assert RealtimeStatus.objects.count() == 1
        saved_status = RealtimeStatus.objects.first()
        assert saved_status.status == RealtimeStatus.Status.AVAILABLE

    def test_sync_status_nonexistent_chargepoint(self):
        """Test that status for non-existent chargepoint is ignored."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        # Try to create status for non-existent chargepoint
        status = make_status("cp_nonexistent", RealtimeStatus.Status.AVAILABLE)
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_1", status)])

        assert RealtimeStatus.objects.count() == 0

    def test_sync_status_nonexistent_site(self):
        """Test that status for non-existent site is ignored."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        # Try to create status for non-existent site
        status = make_status("cp_1", RealtimeStatus.Status.AVAILABLE)
        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, [("site_nonexistent", status)])

        assert RealtimeStatus.objects.count() == 0

    def test_sync_statuses_multiple_sites(self):
        """Test syncing statuses across multiple sites."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])
        create_site_with_chargepoints(STATIC_SOURCE, "site_2", ["cp_2"])

        statuses_data = [
            ("site_1", make_status("cp_1", RealtimeStatus.Status.AVAILABLE)),
            ("site_2", make_status("cp_2", RealtimeStatus.Status.CHARGING)),
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 2

    def test_sync_statuses_different_realtime_sources(self):
        """Test that statuses from different realtime sources are kept separate."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        # Sync status from source 1
        status1 = make_status("cp_1", RealtimeStatus.Status.AVAILABLE)
        sync_statuses("realtime_source_1", STATIC_SOURCE, [("site_1", status1)])

        # Sync status from source 2
        status2 = make_status("cp_1", RealtimeStatus.Status.CHARGING)
        sync_statuses("realtime_source_2", STATIC_SOURCE, [("site_1", status2)])

        assert RealtimeStatus.objects.count() == 2
        assert (
            RealtimeStatus.objects.filter(data_source="realtime_source_1").count() == 1
        )
        assert (
            RealtimeStatus.objects.filter(data_source="realtime_source_2").count() == 1
        )

    def test_sync_statuses_batching_large_dataset(self):
        """Test that large datasets are processed in batches."""
        # Create 150 chargepoints (more than 1 batch of 100)
        for i in range(150):
            create_site_with_chargepoints(STATIC_SOURCE, f"site_{i}", [f"cp_{i}"])

        # Create statuses for all chargepoints
        statuses_data = [
            (f"site_{i}", make_status(f"cp_{i}", RealtimeStatus.Status.AVAILABLE))
            for i in range(150)
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 150
