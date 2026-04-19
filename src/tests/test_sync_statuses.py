"""
Tests for the sync_statuses bulk operations.
"""

from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from evmap_backend.chargers.models import Chargepoint, ChargingSite
from evmap_backend.data_sources.sync import RealtimeStatusItem, sync_statuses
from evmap_backend.realtime.models import RealtimeStatus

STATIC_SOURCE = "test_static_source"
REALTIME_SOURCE = "test_realtime_source"


def make_status_item(site_id, chargepoint_id_from_source, status=None, timestamp=None):
    """Helper function to create RealtimeStatusItem instances."""
    if status is None:
        status = RealtimeStatus.Status.AVAILABLE
    if timestamp is None:
        timestamp = timezone.now()
    return RealtimeStatusItem(
        site_id_from_source=site_id,
        chargepoint_id_from_source=chargepoint_id_from_source,
        status=RealtimeStatus(
            status=status,
            timestamp=timestamp,
        ),
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

        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item("site_1", "cp_1", RealtimeStatus.Status.AVAILABLE),
            ],
        )

        assert RealtimeStatus.objects.count() == 1
        saved_status = RealtimeStatus.objects.first()
        assert saved_status.status == RealtimeStatus.Status.AVAILABLE
        assert saved_status.data_source == REALTIME_SOURCE

    def test_sync_create_multiple_statuses(self):
        """Test creating multiple statuses in a single sync."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1", "cp_2", "cp_3"])

        statuses_data = [
            make_status_item("site_1", "cp_1", RealtimeStatus.Status.AVAILABLE),
            make_status_item("site_1", "cp_2", RealtimeStatus.Status.CHARGING),
            make_status_item("site_1", "cp_3", RealtimeStatus.Status.OUTOFORDER),
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 3

    def test_sync_status_newer_timestamp(self):
        """Test that a newer status is created when timestamp is newer."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        old_time = timezone.now() - timedelta(hours=1)
        new_time = timezone.now()

        # Create initial status
        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item(
                    "site_1", "cp_1", RealtimeStatus.Status.AVAILABLE, old_time
                ),
            ],
        )
        assert RealtimeStatus.objects.count() == 1

        # Create newer status
        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item(
                    "site_1", "cp_1", RealtimeStatus.Status.CHARGING, new_time
                ),
            ],
        )

        assert RealtimeStatus.objects.count() == 2
        latest_status = RealtimeStatus.objects.latest()
        assert latest_status.status == RealtimeStatus.Status.CHARGING

    def test_sync_status_older_timestamp_ignored(self):
        """Test that an older status is ignored when timestamp is older than existing."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        old_time = timezone.now() - timedelta(hours=1)
        new_time = timezone.now()

        # Create initial status with newer timestamp
        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item(
                    "site_1", "cp_1", RealtimeStatus.Status.AVAILABLE, new_time
                ),
            ],
        )
        assert RealtimeStatus.objects.count() == 1

        # Try to create older status - should be ignored
        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item(
                    "site_1", "cp_1", RealtimeStatus.Status.CHARGING, old_time
                ),
            ],
        )

        # Should still be 1 status
        assert RealtimeStatus.objects.count() == 1
        saved_status = RealtimeStatus.objects.first()
        assert saved_status.status == RealtimeStatus.Status.AVAILABLE

    def test_sync_status_nonexistent_chargepoint(self):
        """Test that status for non-existent chargepoint is ignored."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item(
                    "site_1", "cp_nonexistent", RealtimeStatus.Status.AVAILABLE
                ),
            ],
        )

        assert RealtimeStatus.objects.count() == 0

    def test_sync_status_nonexistent_site(self):
        """Test that status for non-existent site is ignored."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                make_status_item(
                    "site_nonexistent", "cp_1", RealtimeStatus.Status.AVAILABLE
                ),
            ],
        )

        assert RealtimeStatus.objects.count() == 0

    def test_sync_statuses_multiple_sites(self):
        """Test syncing statuses across multiple sites."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])
        create_site_with_chargepoints(STATIC_SOURCE, "site_2", ["cp_2"])

        statuses_data = [
            make_status_item("site_1", "cp_1", RealtimeStatus.Status.AVAILABLE),
            make_status_item("site_2", "cp_2", RealtimeStatus.Status.CHARGING),
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 2

    def test_sync_statuses_different_realtime_sources(self):
        """Test that statuses from different realtime sources are kept separate."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        # Sync status from source 1
        sync_statuses(
            "realtime_source_1",
            STATIC_SOURCE,
            [
                make_status_item("site_1", "cp_1", RealtimeStatus.Status.AVAILABLE),
            ],
        )

        # Sync status from source 2
        sync_statuses(
            "realtime_source_2",
            STATIC_SOURCE,
            [
                make_status_item("site_1", "cp_1", RealtimeStatus.Status.CHARGING),
            ],
        )

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
            make_status_item(f"site_{i}", f"cp_{i}", RealtimeStatus.Status.AVAILABLE)
            for i in range(150)
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 150

    def test_sync_status_without_site_id(self):
        """Test creating a status without site_id_from_source when chargepoint ID is unique."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                RealtimeStatusItem(
                    chargepoint_id_from_source="cp_1",
                    status=RealtimeStatus(
                        status=RealtimeStatus.Status.AVAILABLE,
                        timestamp=timezone.now(),
                    ),
                ),
            ],
        )

        assert RealtimeStatus.objects.count() == 1
        saved_status = RealtimeStatus.objects.first()
        assert saved_status.status == RealtimeStatus.Status.AVAILABLE
        assert saved_status.data_source == REALTIME_SOURCE

    def test_sync_status_without_site_id_multiple(self):
        """Test creating multiple statuses without site_id_from_source."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1", "cp_2"])
        create_site_with_chargepoints(STATIC_SOURCE, "site_2", ["cp_3"])

        statuses_data = [
            RealtimeStatusItem(
                chargepoint_id_from_source="cp_1",
                status=RealtimeStatus(
                    status=RealtimeStatus.Status.AVAILABLE, timestamp=timezone.now()
                ),
            ),
            RealtimeStatusItem(
                chargepoint_id_from_source="cp_2",
                status=RealtimeStatus(
                    status=RealtimeStatus.Status.CHARGING, timestamp=timezone.now()
                ),
            ),
            RealtimeStatusItem(
                chargepoint_id_from_source="cp_3",
                status=RealtimeStatus(
                    status=RealtimeStatus.Status.OUTOFORDER, timestamp=timezone.now()
                ),
            ),
        ]

        sync_statuses(REALTIME_SOURCE, STATIC_SOURCE, statuses_data)

        assert RealtimeStatus.objects.count() == 3

    def test_sync_status_without_site_id_nonexistent_chargepoint(self):
        """Test that status without site_id for non-existent chargepoint is ignored."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_1"])

        sync_statuses(
            REALTIME_SOURCE,
            STATIC_SOURCE,
            [
                RealtimeStatusItem(
                    chargepoint_id_from_source="cp_nonexistent",
                    status=RealtimeStatus(
                        status=RealtimeStatus.Status.AVAILABLE, timestamp=timezone.now()
                    ),
                ),
            ],
        )

        assert RealtimeStatus.objects.count() == 0

    def test_sync_status_without_site_id_duplicate_cp_raises(self):
        """Test that status without site_id raises when chargepoint ID is not unique across sites."""
        create_site_with_chargepoints(STATIC_SOURCE, "site_1", ["cp_shared"])
        create_site_with_chargepoints(STATIC_SOURCE, "site_2", ["cp_shared"])

        with pytest.raises(ValueError, match="not unique"):
            sync_statuses(
                REALTIME_SOURCE,
                STATIC_SOURCE,
                [
                    RealtimeStatusItem(
                        chargepoint_id_from_source="cp_shared",
                        status=RealtimeStatus(
                            status=RealtimeStatus.Status.AVAILABLE,
                            timestamp=timezone.now(),
                        ),
                    ),
                ],
            )
