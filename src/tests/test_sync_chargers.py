"""
Tests for the sync_chargers bulk operations.
"""

import pytest

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector
from evmap_backend.sync import sync_chargers


@pytest.mark.django_db(transaction=True)
class TestSyncChargers:
    def test_sync_empty_data(self, data_source):
        """Test syncing with empty data."""
        sync_chargers(data_source, [])

        assert ChargingSite.objects.count() == 0
        assert Chargepoint.objects.count() == 0
        assert Connector.objects.count() == 0

    def test_sync_create_single_site(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test creating a single site with chargepoints and connectors."""
        site = create_site("site_1", name="Site 1")
        cp = create_chargepoint("cp_1")
        conn = create_connector(
            "conn_1", connector_type=Connector.ConnectorTypes.TYPE_2
        )

        sync_chargers(data_source, [(site, [(cp, [conn])])])

        # Verify site created
        assert ChargingSite.objects.count() == 1
        saved_site = ChargingSite.objects.get(
            data_source=data_source, id_from_source="site_1"
        )
        assert saved_site.name == "Site 1"

        # Verify chargepoint created
        assert Chargepoint.objects.count() == 1
        saved_cp = Chargepoint.objects.get(site=saved_site, id_from_source="cp_1")

        # Verify connector created
        assert Connector.objects.count() == 1
        saved_conn = Connector.objects.get(
            chargepoint=saved_cp, id_from_source="conn_1"
        )
        assert saved_conn.connector_type == Connector.ConnectorTypes.TYPE_2

    def test_sync_create_multiple_sites(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test creating multiple sites in a single sync."""
        sites_data = []
        for i in range(5):
            site = create_site(f"site_{i}", name=f"Site {i}")
            cp = create_chargepoint(f"cp_{i}")
            conn = create_connector(f"conn_{i}")
            sites_data.append((site, [(cp, [conn])]))

        sync_chargers(data_source, sites_data)

        assert ChargingSite.objects.count() == 5
        assert Chargepoint.objects.count() == 5
        assert Connector.objects.count() == 5

    def test_sync_update_existing_site(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test updating an existing site."""
        # Create initial site
        site = create_site("site_1", name="Original Name")
        cp = create_chargepoint("cp_1")
        conn = create_connector("conn_1")
        sync_chargers(data_source, [(site, [(cp, [conn])])])

        # Update site
        updated_site = create_site("site_1", name="Updated Name", city="Berlin")
        updated_cp = create_chargepoint("cp_1")
        updated_conn = create_connector("conn_1", max_power=50000.0)
        sync_chargers(data_source, [(updated_site, [(updated_cp, [updated_conn])])])

        # Verify update (should still be 1 site)
        assert ChargingSite.objects.count() == 1
        saved_site = ChargingSite.objects.get(
            data_source=data_source, id_from_source="site_1"
        )
        assert saved_site.name == "Updated Name"
        assert saved_site.city == "Berlin"

        # Verify connector was updated
        assert Connector.objects.count() == 1
        saved_conn = Connector.objects.get(chargepoint__site=saved_site)
        assert saved_conn.max_power == 50000.0

    def test_sync_delete_missing_site(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test that sites not in the sync data are deleted."""
        # Create initial sites
        site1 = create_site("site_1")
        site2 = create_site("site_2")
        cp1 = create_chargepoint("cp_1")
        cp2 = create_chargepoint("cp_2")
        conn1 = create_connector("conn_1")
        conn2 = create_connector("conn_2")

        sync_chargers(
            data_source,
            [
                (site1, [(cp1, [conn1])]),
                (site2, [(cp2, [conn2])]),
            ],
        )
        assert ChargingSite.objects.count() == 2

        # Sync only site_1, site_2 should be deleted
        updated_site1 = create_site("site_1")
        updated_cp1 = create_chargepoint("cp_1")
        updated_conn1 = create_connector("conn_1")
        sync_chargers(data_source, [(updated_site1, [(updated_cp1, [updated_conn1])])])

        assert ChargingSite.objects.count() == 1
        assert ChargingSite.objects.filter(id_from_source="site_1").exists()
        assert not ChargingSite.objects.filter(id_from_source="site_2").exists()

    def test_sync_delete_missing_chargepoints(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test that chargepoints not in the sync data are deleted."""
        # Create site with 2 chargepoints
        site = create_site("site_1")
        cp1 = create_chargepoint("cp_1")
        cp2 = create_chargepoint("cp_2")
        conn1 = create_connector("conn_1")
        conn2 = create_connector("conn_2")

        sync_chargers(data_source, [(site, [(cp1, [conn1]), (cp2, [conn2])])])
        assert Chargepoint.objects.count() == 2

        # Sync with only cp_1, cp_2 should be deleted
        updated_site = create_site("site_1")
        updated_cp1 = create_chargepoint("cp_1")
        updated_conn1 = create_connector("conn_1")
        sync_chargers(data_source, [(updated_site, [(updated_cp1, [updated_conn1])])])

        assert Chargepoint.objects.count() == 1
        saved_site = ChargingSite.objects.get(id_from_source="site_1")
        assert Chargepoint.objects.filter(
            site=saved_site, id_from_source="cp_1"
        ).exists()
        assert not Chargepoint.objects.filter(
            site=saved_site, id_from_source="cp_2"
        ).exists()

    def test_sync_delete_missing_connectors(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test that connectors not in the sync data are deleted."""
        # Create chargepoint with 2 connectors
        site = create_site("site_1")
        cp = create_chargepoint("cp_1")
        conn1 = create_connector("conn_1")
        conn2 = create_connector("conn_2")

        sync_chargers(data_source, [(site, [(cp, [conn1, conn2])])])
        assert Connector.objects.count() == 2

        # Sync with only conn_1, conn_2 should be deleted
        updated_site = create_site("site_1")
        updated_cp = create_chargepoint("cp_1")
        updated_conn1 = create_connector("conn_1")
        sync_chargers(data_source, [(updated_site, [(updated_cp, [updated_conn1])])])

        assert Connector.objects.count() == 1
        saved_cp = Chargepoint.objects.get(id_from_source="cp_1")
        assert Connector.objects.filter(
            chargepoint=saved_cp, id_from_source="conn_1"
        ).exists()
        assert not Connector.objects.filter(
            chargepoint=saved_cp, id_from_source="conn_2"
        ).exists()

    def test_sync_multiple_chargepoints_per_site(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test site with multiple chargepoints."""
        site = create_site("site_1")
        cp1 = create_chargepoint("cp_1")
        cp2 = create_chargepoint("cp_2")
        cp3 = create_chargepoint("cp_3")
        conn1 = create_connector("conn_1")
        conn2 = create_connector("conn_2")
        conn3 = create_connector("conn_3")

        sync_chargers(
            data_source, [(site, [(cp1, [conn1]), (cp2, [conn2]), (cp3, [conn3])])]
        )

        assert ChargingSite.objects.count() == 1
        assert Chargepoint.objects.count() == 3
        assert Connector.objects.count() == 3

    def test_sync_multiple_connectors_per_chargepoint(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test chargepoint with multiple connectors."""
        site = create_site("site_1")
        cp = create_chargepoint("cp_1")
        conn1 = create_connector(
            "conn_1", connector_type=Connector.ConnectorTypes.TYPE_2
        )
        conn2 = create_connector(
            "conn_2", connector_type=Connector.ConnectorTypes.CCS_TYPE_2
        )
        conn3 = create_connector(
            "conn_3", connector_type=Connector.ConnectorTypes.CHADEMO
        )

        sync_chargers(data_source, [(site, [(cp, [conn1, conn2, conn3])])])

        assert Connector.objects.count() == 3
        saved_cp = Chargepoint.objects.get(id_from_source="cp_1")
        assert saved_cp.connectors.count() == 3

    def test_sync_connectors_without_ids(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test syncing connectors without id_from_source (fallback logic)."""
        site = create_site("site_1")
        cp = create_chargepoint("cp_1")
        conn1 = create_connector(None, connector_type=Connector.ConnectorTypes.TYPE_2)
        conn2 = create_connector(
            None, connector_type=Connector.ConnectorTypes.CCS_TYPE_2
        )

        sync_chargers(data_source, [(site, [(cp, [conn1, conn2])])])

        assert Connector.objects.count() == 2
        saved_cp = Chargepoint.objects.get(id_from_source="cp_1")
        assert saved_cp.connectors.count() == 2

    def test_sync_connectors_without_ids_no_change(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test that connectors without IDs are not recreated if they match."""
        site = create_site("site_1")
        cp = create_chargepoint("cp_1")
        conn1 = create_connector(
            None, connector_type=Connector.ConnectorTypes.TYPE_2, max_power=22000.0
        )
        conn2 = create_connector(
            None, connector_type=Connector.ConnectorTypes.CCS_TYPE_2, max_power=50000.0
        )

        # First sync
        sync_chargers(data_source, [(site, [(cp, [conn1, conn2])])])
        first_connector_ids = set(Connector.objects.values_list("id", flat=True))

        # Second sync with same data
        updated_site = create_site("site_1")
        updated_cp = create_chargepoint("cp_1")
        updated_conn1 = create_connector(
            None, connector_type=Connector.ConnectorTypes.TYPE_2, max_power=22000.0
        )
        updated_conn2 = create_connector(
            None, connector_type=Connector.ConnectorTypes.CCS_TYPE_2, max_power=50000.0
        )
        sync_chargers(
            data_source,
            [(updated_site, [(updated_cp, [updated_conn1, updated_conn2])])],
        )

        # Connector IDs should be the same (not recreated)
        second_connector_ids = set(Connector.objects.values_list("id", flat=True))
        assert first_connector_ids == second_connector_ids
        assert Connector.objects.count() == 2

    def test_sync_connectors_without_ids_with_change(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test that connectors without IDs are recreated if they change."""
        site = create_site("site_1")
        cp = create_chargepoint("cp_1")
        conn1 = create_connector(None, connector_type=Connector.ConnectorTypes.TYPE_2)

        # First sync
        sync_chargers(data_source, [(site, [(cp, [conn1])])])
        assert Connector.objects.count() == 1

        # Second sync with different connector
        updated_site = create_site("site_1")
        updated_cp = create_chargepoint("cp_1")
        updated_conn1 = create_connector(
            None, connector_type=Connector.ConnectorTypes.CCS_TYPE_2
        )
        sync_chargers(data_source, [(updated_site, [(updated_cp, [updated_conn1])])])

        # Should still be 1 connector but recreated
        assert Connector.objects.count() == 1
        saved_conn = Connector.objects.first()
        assert saved_conn.connector_type == Connector.ConnectorTypes.CCS_TYPE_2

    def test_sync_batching_large_dataset(
        self, data_source, create_site, create_chargepoint, create_connector
    ):
        """Test that large datasets are processed in batches."""
        # Create 250 sites (more than 2 batches of 100)
        sites_data = []
        for i in range(250):
            site = create_site(f"site_{i}", name=f"Site {i}")
            cp = create_chargepoint(f"cp_{i}")
            conn = create_connector(f"conn_{i}")
            sites_data.append((site, [(cp, [conn])]))

        sync_chargers(data_source, sites_data)

        assert ChargingSite.objects.count() == 250
        assert Chargepoint.objects.count() == 250
        assert Connector.objects.count() == 250

    def test_sync_multiple_data_sources(
        self, create_site, create_chargepoint, create_connector
    ):
        """Test that sites from different data sources are kept separate."""
        site1 = create_site("site_1")
        cp1 = create_chargepoint("cp_1")
        conn1 = create_connector("conn_1")
        sync_chargers("source_1", [(site1, [(cp1, [conn1])])])

        site2 = create_site("site_1")  # Same ID but different source
        cp2 = create_chargepoint("cp_1")
        conn2 = create_connector("conn_1")
        sync_chargers("source_2", [(site2, [(cp2, [conn2])])])

        assert ChargingSite.objects.count() == 2
        assert ChargingSite.objects.filter(data_source="source_1").count() == 1
        assert ChargingSite.objects.filter(data_source="source_2").count() == 1

        # Sync source_1 with empty data - should only delete source_1 sites
        sync_chargers("source_1", [])

        assert ChargingSite.objects.count() == 1
        assert ChargingSite.objects.filter(data_source="source_2").count() == 1
