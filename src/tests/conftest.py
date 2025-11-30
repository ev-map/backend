"""
Pytest configuration and shared fixtures.
"""

import pytest
from django.contrib.gis.geos import Point

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector


@pytest.fixture
def data_source():
    """Fixture for a test data source name."""
    return "test_source"


@pytest.fixture
def test_location():
    """Fixture for a test location point."""
    return Point(10.0, 50.0)


@pytest.fixture
def create_site(test_location):
    """Fixture that returns a function to create ChargingSite instances."""

    def _create_site(id_from_source, name="Test Site", **kwargs):
        return ChargingSite(
            id_from_source=id_from_source,
            name=name,
            location=kwargs.get("location", test_location),
            country=kwargs.get("country", "DE"),
            street=kwargs.get("street", ""),
            zipcode=kwargs.get("zipcode", ""),
            city=kwargs.get("city", ""),
            network=kwargs.get("network", ""),
            operator=kwargs.get("operator", ""),
        )

    return _create_site


@pytest.fixture
def create_chargepoint():
    """Fixture that returns a function to create Chargepoint instances."""

    def _create_chargepoint(id_from_source, **kwargs):
        return Chargepoint(
            id_from_source=id_from_source,
            evseid=kwargs.get("evseid", ""),
        )

    return _create_chargepoint


@pytest.fixture
def create_connector():
    """Fixture that returns a function to create Connector instances."""

    def _create_connector(id_from_source="", connector_type=None, **kwargs):
        if connector_type is None:
            connector_type = Connector.ConnectorTypes.TYPE_2
        return Connector(
            id_from_source=id_from_source,
            connector_type=connector_type,
            connector_format=kwargs.get(
                "connector_format", Connector.ConnectorFormats.SOCKET
            ),
            max_power=kwargs.get("max_power", 22000.0),
        )

    return _create_connector
