"""
Tests for GoingElectric matching algorithm.
"""

import pytest
from django.contrib.gis.geos import Point

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources.goingelectric.matching import (
    _power_matches,
    _score_chargepoints,
    _score_distance,
    _score_network,
    match_ge_locations,
)
from evmap_backend.data_sources.goingelectric.models import (
    GoingElectricChargeLocation,
    GoingElectricChargepoint,
    GoingElectricNetwork,
)


@pytest.fixture
def ge_network():
    """Create a GoingElectric network."""
    return GoingElectricNetwork.objects.create(name="TestNetwork")


@pytest.fixture
def charger_network():
    """Create a chargers.Network."""
    return Network.objects.create(name="TestNetwork", evse_operator_id="DETST")


@pytest.fixture
def mapped_ge_network(ge_network, charger_network):
    """Create a GE network with a mapped charger network."""
    ge_network.mapped_networks.add(charger_network)
    return ge_network


@pytest.fixture
def base_location():
    """Base location point for tests (Berlin)."""
    return Point(13.4050, 52.5200, srid=4326)


def _offset_point(base: Point, offset_m: float) -> Point:
    """Create a point offset from base by approximately offset_m meters east."""
    # At ~52° latitude, 1 degree longitude ≈ 67km
    offset_deg = offset_m / 67000.0
    return Point(base.x + offset_deg, base.y, srid=4326)


def _create_ge_location(ge_id, coordinates, network=None, name="Test GE Location"):
    """Helper to create a GoingElectricChargeLocation."""
    return GoingElectricChargeLocation.objects.create(
        id=ge_id,
        name=name,
        coordinates=coordinates,
        network=network,
        url=f"https://example.com/{ge_id}",
        fault_report=False,
        verified=True,
    )


def _create_ge_chargepoint(location, connector_type, power_kw, count=1):
    """Helper to create a GoingElectricChargepoint."""
    return GoingElectricChargepoint.objects.create(
        chargelocation=location,
        type=connector_type,
        power=power_kw,
        count=count,
    )


def _create_charging_site(
    id_from_source, location, network=None, data_source="test_source"
):
    """Helper to create a ChargingSite."""
    return ChargingSite.objects.create(
        data_source=data_source,
        id_from_source=id_from_source,
        name=f"Site {id_from_source}",
        location=location,
        country="DE",
        network=network,
    )


def _create_connector(site, connector_type, max_power_w):
    """Helper to create a Connector on a site (with intermediate Chargepoint)."""
    cp, _ = Chargepoint.objects.get_or_create(
        site=site,
        id_from_source=f"cp_{site.id_from_source}_{connector_type}",
    )
    return Connector.objects.create(
        chargepoint=cp,
        connector_type=connector_type,
        max_power=max_power_w,
    )


# --- Unit tests for scoring functions ---


class TestScoreDistance:
    def test_zero_distance(self):
        assert _score_distance(0.0, 200.0) == 1.0

    def test_max_distance(self):
        assert _score_distance(200.0, 200.0) == 0.0

    def test_half_distance(self):
        assert _score_distance(100.0, 200.0) == pytest.approx(0.5)

    def test_over_max_distance(self):
        assert _score_distance(300.0, 200.0) == 0.0


class TestPowerMatches:
    def test_equal_power(self):
        assert _power_matches(22000, 22000) is True

    def test_11kw_vs_22kw(self):
        """Key real-world case: 11kW at GE, 22kW at other source."""
        assert _power_matches(11000, 22000) is True

    def test_22kw_vs_11kw(self):
        assert _power_matches(22000, 11000) is True

    def test_too_far_apart(self):
        """50kW vs 150kW should not match (ratio > 2)."""
        assert _power_matches(50000, 150000) is False

    def test_zero_power(self):
        """Zero power should not penalize."""
        assert _power_matches(0, 22000) is True
        assert _power_matches(22000, 0) is True


class TestScoreNetwork:
    def test_both_none(self):
        assert _score_network(None, None, {}) == 0.5

    def test_ge_none(self):
        assert _score_network(None, 1, {}) == 0.5

    def test_site_none(self):
        assert _score_network(1, None, {1: {2}}) == 0.5

    def test_match(self):
        assert _score_network(1, 2, {1: {2, 3}}) == 1.0

    def test_no_match(self):
        assert _score_network(1, 4, {1: {2, 3}}) == 0.0

    def test_no_mapping_configured(self):
        """GE network exists but has no mapped_networks — treat as unknown."""
        assert _score_network(1, 2, {}) == 0.5


class TestScoreChargepoints:
    def test_no_ge_chargepoints(self):
        assert _score_chargepoints([], []) == 0.5

    def test_no_site_connectors(self):
        ge_cp = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.TYPE_2,
            power=22.0,
            count=1,
        )
        assert _score_chargepoints([ge_cp], []) == 0.0

    def test_exact_match(self):
        ge_cp = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.TYPE_2,
            power=22.0,
            count=1,
        )
        site_conn = Connector(
            connector_type=Connector.ConnectorTypes.TYPE_2,
            max_power=22000.0,
        )
        assert _score_chargepoints([ge_cp], [site_conn]) == 1.0

    def test_power_tolerance_11_vs_22(self):
        """11kW GE chargepoint should match 22kW site connector."""
        ge_cp = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.TYPE_2,
            power=11.0,
            count=1,
        )
        site_conn = Connector(
            connector_type=Connector.ConnectorTypes.TYPE_2,
            max_power=22000.0,
        )
        assert _score_chargepoints([ge_cp], [site_conn]) == 1.0

    def test_ccs_unknown_matches_ccs_type_2(self):
        """GE CCS (unknown variant) should match CCS Type 2."""
        ge_cp = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.CCS,
            power=50.0,
            count=1,
        )
        site_conn = Connector(
            connector_type=Connector.ConnectorTypes.CCS_TYPE_2,
            max_power=50000.0,
        )
        assert _score_chargepoints([ge_cp], [site_conn]) == 1.0

    def test_partial_match(self):
        """One of two GE chargepoints matches."""
        ge_cp1 = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.TYPE_2,
            power=22.0,
            count=1,
        )
        ge_cp2 = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.CHADEMO,
            power=50.0,
            count=1,
        )
        site_conn = Connector(
            connector_type=Connector.ConnectorTypes.TYPE_2,
            max_power=22000.0,
        )
        assert _score_chargepoints([ge_cp1, ge_cp2], [site_conn]) == pytest.approx(0.5)

    def test_type_mismatch(self):
        ge_cp = GoingElectricChargepoint(
            type=GoingElectricChargepoint.ConnectorTypes.CHADEMO,
            power=50.0,
            count=1,
        )
        site_conn = Connector(
            connector_type=Connector.ConnectorTypes.TYPE_2,
            max_power=22000.0,
        )
        assert _score_chargepoints([ge_cp], [site_conn]) == 0.0


# --- Integration tests for match_ge_locations ---


@pytest.mark.django_db(transaction=True)
class TestMatchGeLocations:
    def test_exact_location_match(self, base_location, charger_network):
        """GE location at exact same coordinates as ChargingSite."""
        site = _create_charging_site("s1", base_location, network=charger_network)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc = _create_ge_location(1, base_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site == site
        assert ge_loc.match_confidence is not None
        assert ge_loc.match_confidence > 0.5

    def test_nearby_offset_match(self, base_location, charger_network):
        """GE location offset by ~50m from ChargingSite."""
        site = _create_charging_site("s1", base_location, network=charger_network)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        offset_location = _offset_point(base_location, 50)
        ge_loc = _create_ge_location(1, offset_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site == site
        assert ge_loc.match_confidence is not None

    def test_no_match_too_far(self, base_location):
        """GE location too far from any ChargingSite."""
        site = _create_charging_site("s1", base_location)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        far_location = _offset_point(base_location, 500)
        ge_loc = _create_ge_location(1, far_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site is None
        assert ge_loc.match_confidence is None

    def test_network_boosts_match(
        self, base_location, mapped_ge_network, charger_network
    ):
        """Network match should boost confidence score."""
        site = _create_charging_site("s1", base_location, network=charger_network)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc = _create_ge_location(1, base_location, network=mapped_ge_network)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site == site
        assert ge_loc.match_confidence is not None
        # With network match, confidence should be high
        assert ge_loc.match_confidence > 0.8

    def test_chargepoint_power_tolerance(self, base_location):
        """11kW GE chargepoint should match 22kW site (factor of 2 tolerance)."""
        site = _create_charging_site("s1", base_location)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc = _create_ge_location(1, base_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 11.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site == site

    def test_competing_ge_locations_higher_score_wins(
        self, base_location, mapped_ge_network, charger_network
    ):
        """Two GE locations near the same site — higher-scoring one wins."""
        site = _create_charging_site("s1", base_location, network=charger_network)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        # GE location 1: exact location + matching network + matching chargepoints
        ge_loc1 = _create_ge_location(1, base_location, network=mapped_ge_network)
        _create_ge_chargepoint(
            ge_loc1, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        # GE location 2: slightly offset, no network, different chargepoint type
        offset_location = _offset_point(base_location, 100)
        ge_loc2 = _create_ge_location(2, offset_location)
        _create_ge_chargepoint(
            ge_loc2, GoingElectricChargepoint.ConnectorTypes.CHADEMO, 50.0
        )

        match_ge_locations()

        ge_loc1.refresh_from_db()
        ge_loc2.refresh_from_db()

        # GE location 1 should win the match (better score)
        assert ge_loc1.matched_site == site
        # GE location 2 should be unmatched (site already claimed)
        assert ge_loc2.matched_site is None

    def test_one_to_one_constraint(self, base_location):
        """Each ChargingSite can be matched by at most one GE location."""
        site = _create_charging_site("s1", base_location)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc1 = _create_ge_location(1, base_location)
        _create_ge_chargepoint(
            ge_loc1, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        ge_loc2 = _create_ge_location(2, base_location)
        _create_ge_chargepoint(
            ge_loc2, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc1.refresh_from_db()
        ge_loc2.refresh_from_db()

        # Only one should have the match
        matched = [loc for loc in [ge_loc1, ge_loc2] if loc.matched_site is not None]
        assert len(matched) == 1
        assert matched[0].matched_site == site

    def test_deterministic_results(self, base_location):
        """Running matching twice with same data produces same results."""
        site = _create_charging_site("s1", base_location)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc = _create_ge_location(1, base_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()
        ge_loc.refresh_from_db()
        first_match = ge_loc.matched_site_id
        first_confidence = ge_loc.match_confidence

        match_ge_locations()
        ge_loc.refresh_from_db()
        assert ge_loc.matched_site_id == first_match
        assert ge_loc.match_confidence == first_confidence

    def test_stale_matches_cleared(self, base_location):
        """Previously matched GE location should be unmatched if site disappears."""
        site = _create_charging_site("s1", base_location)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc = _create_ge_location(1, base_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()
        ge_loc.refresh_from_db()
        assert ge_loc.matched_site == site

        # Delete the site
        site.delete()

        match_ge_locations()
        ge_loc.refresh_from_db()
        assert ge_loc.matched_site is None
        assert ge_loc.match_confidence is None

    def test_below_threshold_no_match(self, base_location):
        """Pair with score below threshold should not be matched."""
        site = _create_charging_site("s1", base_location)
        _create_connector(site, Connector.ConnectorTypes.TYPE_2, 22000)

        # GE location nearby but with completely wrong chargepoint type
        ge_loc = _create_ge_location(1, _offset_point(base_location, 150))
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.CHADEMO, 50.0
        )

        # Use a high threshold
        match_ge_locations(min_confidence=0.9)

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site is None

    def test_multiple_sites_correct_assignment(self, base_location):
        """Two GE locations should match their respective nearest sites."""
        loc1 = base_location
        loc2 = _offset_point(base_location, 500)

        site1 = _create_charging_site("s1", loc1)
        _create_connector(site1, Connector.ConnectorTypes.TYPE_2, 22000)

        site2 = _create_charging_site("s2", loc2)
        _create_connector(site2, Connector.ConnectorTypes.TYPE_2, 22000)

        ge_loc1 = _create_ge_location(1, loc1)
        _create_ge_chargepoint(
            ge_loc1, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        ge_loc2 = _create_ge_location(2, loc2)
        _create_ge_chargepoint(
            ge_loc2, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc1.refresh_from_db()
        ge_loc2.refresh_from_db()

        assert ge_loc1.matched_site == site1
        assert ge_loc2.matched_site == site2

    def test_network_m2m_multiple_networks(self, base_location):
        """GE network mapped to multiple charger Networks should match any of them."""
        ge_net = GoingElectricNetwork.objects.create(name="IONITY")
        net_de = Network.objects.create(name="IONITY DE", evse_operator_id="DEION")
        net_at = Network.objects.create(name="IONITY AT", evse_operator_id="ATION")
        ge_net.mapped_networks.add(net_de, net_at)

        # Site with the AT network
        site = _create_charging_site("s1", base_location, network=net_at)
        _create_connector(site, Connector.ConnectorTypes.CCS_TYPE_2, 350000)

        ge_loc = _create_ge_location(1, base_location, network=ge_net)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.CCS, 350.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site == site
        assert ge_loc.match_confidence is not None
        assert ge_loc.match_confidence > 0.8

    def test_no_ge_locations(self):
        """Should handle empty GE location table gracefully."""
        match_ge_locations()
        # No error raised

    def test_no_charging_sites(self, base_location):
        """GE locations with no nearby charging sites remain unmatched."""
        ge_loc = _create_ge_location(1, base_location)
        _create_ge_chargepoint(
            ge_loc, GoingElectricChargepoint.ConnectorTypes.TYPE_2, 22.0
        )

        match_ge_locations()

        ge_loc.refresh_from_db()
        assert ge_loc.matched_site is None
