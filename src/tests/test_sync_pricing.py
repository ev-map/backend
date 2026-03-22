from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point

from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.data_sources.datex2.parser import (
    Datex2EnergyPrice,
    Datex2EnergyRate,
    Datex2RefillPointPricing,
    Datex2SitePricing,
)
from evmap_backend.pricing.models import PriceComponent, Tariff
from evmap_backend.pricing.sync import sync_pricing


@pytest.fixture
def network(db):
    return Network.objects.create(name="TestNetwork", evse_operator_id="DEABC")


@pytest.fixture
def site_with_chargepoints(db, network):
    """Create a site with two chargepoints (one AC, one DC)."""
    site = ChargingSite.objects.create(
        data_source="test_static",
        id_from_source="site-1",
        name="Test Site",
        location=Point(10.0, 50.0),
        country="DE",
        network=network,
    )
    cp1 = Chargepoint.objects.create(
        site=site,
        id_from_source="DE*ABC*E0001*1",
    )
    Connector.objects.create(
        chargepoint=cp1,
        connector_type=Connector.ConnectorTypes.TYPE_2,
        max_power=22000,
    )
    cp2 = Chargepoint.objects.create(
        site=site,
        id_from_source="DE*ABC*E0001*2",
    )
    Connector.objects.create(
        chargepoint=cp2,
        connector_type=Connector.ConnectorTypes.CCS_TYPE_2,
        max_power=150000,
    )
    return site, cp1, cp2


def _convert_site_pricings(site_pricings, data_source="test_pricing"):
    """Helper: convert Datex2SitePricing objects to the tuples sync_pricing expects."""
    for sp in site_pricings:
        yield from sp.convert(data_source)


@pytest.fixture
def simple_energy_rate():
    """Simple EnBW-style ad-hoc rate: per-kWh only."""
    return Datex2EnergyRate(
        id="adHoc",
        rate_policy="adHoc",
        currencies=["EUR"],
        prices=[
            Datex2EnergyPrice(
                price_type=Datex2EnergyPrice.PriceType.PRICE_PER_KWH,
                value=0.39,
                tax_included=False,
                tax_rate=19.0,
            ),
        ],
    )


@pytest.fixture
def rate_with_time_component():
    """EnBW-style ad-hoc rate: per-kWh + per-minute after 30 min."""
    return Datex2EnergyRate(
        id="adHoc",
        rate_policy="adHoc",
        currencies=["EUR"],
        prices=[
            Datex2EnergyPrice(
                price_type=Datex2EnergyPrice.PriceType.PRICE_PER_KWH,
                value=0.66386555,
                tax_included=False,
                tax_rate=19.0,
            ),
            Datex2EnergyPrice(
                price_type=Datex2EnergyPrice.PriceType.PRICE_PER_MINUTE,
                value=0.20,
                tax_included=False,
                tax_rate=19.0,
                from_minute=30,
                to_minute=0,
            ),
        ],
    )


@pytest.mark.django_db
class TestDatex2PricingConvert:
    """Test the Datex2 -> Tariff/PriceComponent conversion."""

    def test_simple_rate_convert(self, simple_energy_rate):
        tariff, components = simple_energy_rate.convert("test_src")
        assert tariff.is_adhoc is True
        assert tariff.currency == "EUR"
        assert tariff.id_from_source is None
        assert len(components) == 1
        assert components[0].type == PriceComponent.PriceComponentType.ENERGY
        assert components[0].price == Decimal("0.39")
        assert components[0].tax_included is False
        assert components[0].tax_rate == Decimal("19.00")

    def test_time_component_convert(self, rate_with_time_component):
        tariff, components = rate_with_time_component.convert("test_src")
        assert len(components) == 2
        energy = next(
            c for c in components if c.type == PriceComponent.PriceComponentType.ENERGY
        )
        time = next(
            c for c in components if c.type == PriceComponent.PriceComponentType.TIME
        )
        assert energy.price == Decimal("0.66386555")
        assert energy.min_duration is None
        assert time.price == Decimal("0.2")
        assert time.min_duration == 30 * 60
        assert time.max_duration is None  # toMinute=0 means no upper limit

    def test_site_pricing_convert(self, simple_energy_rate):
        sp = Datex2SitePricing(
            site_id="site-1",
            refill_point_pricings=[
                Datex2RefillPointPricing(
                    refill_point_id="cp-1",
                    energy_rates=[simple_energy_rate],
                ),
                Datex2RefillPointPricing(
                    refill_point_id="cp-2",
                    energy_rates=[simple_energy_rate],
                ),
            ],
        )
        items = sp.convert("test_src")
        assert len(items) == 2
        assert items[0][0] == "site-1"
        assert items[0][1] == "cp-1"
        assert items[1][1] == "cp-2"
        assert isinstance(items[0][2], Tariff)
        assert isinstance(items[0][3], list)


@pytest.mark.django_db
class TestSyncPricing:
    def test_basic_sync(self, site_with_chargepoints, simple_energy_rate):
        site, cp1, cp2 = site_with_chargepoints

        site_pricings = [
            Datex2SitePricing(
                site_id="site-1",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*1",
                        energy_rates=[simple_energy_rate],
                    ),
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*2",
                        energy_rates=[simple_energy_rate],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings),
        )

        # Both CPs have the same rate => one tariff
        assert Tariff.objects.count() == 1
        tariff = Tariff.objects.first()
        assert tariff.currency == "EUR"
        assert tariff.is_adhoc is True
        assert tariff.data_source == "test_pricing"
        assert tariff.chargepoints.count() == 2

        # One price component
        assert tariff.price_components.count() == 1
        pc = tariff.price_components.first()
        assert pc.type == PriceComponent.PriceComponentType.ENERGY
        assert float(pc.price) == pytest.approx(0.39)
        assert pc.tax_included is False
        assert pc.tax_rate == Decimal("19.00")
        assert pc.min_duration is None
        assert pc.max_duration is None

    def test_time_based_applicability(
        self, site_with_chargepoints, rate_with_time_component
    ):
        site, cp1, cp2 = site_with_chargepoints

        site_pricings = [
            Datex2SitePricing(
                site_id="site-1",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*1",
                        energy_rates=[rate_with_time_component],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings),
        )

        tariff = Tariff.objects.first()
        assert tariff.price_components.count() == 2

        energy_pc = tariff.price_components.get(
            type=PriceComponent.PriceComponentType.ENERGY
        )
        assert float(energy_pc.price) == pytest.approx(0.66386555)
        assert energy_pc.min_duration is None

        time_pc = tariff.price_components.get(
            type=PriceComponent.PriceComponentType.TIME
        )
        assert float(time_pc.price) == pytest.approx(0.20)
        assert time_pc.min_duration == 30 * 60  # 30 minutes in seconds
        assert time_pc.max_duration is None  # toMinute=0 means no upper limit

    def test_deduplication(self, site_with_chargepoints, simple_energy_rate):
        """Chargepoints with identical pricing should share a single tariff."""
        site, cp1, cp2 = site_with_chargepoints

        site_pricings = [
            Datex2SitePricing(
                site_id="site-1",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*1",
                        energy_rates=[simple_energy_rate],
                    ),
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*2",
                        energy_rates=[simple_energy_rate],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings),
        )
        assert Tariff.objects.count() == 1
        assert Tariff.objects.first().chargepoints.count() == 2

    def test_different_tariffs(self, site_with_chargepoints):
        """Chargepoints with different pricing should get separate tariffs."""
        site, cp1, cp2 = site_with_chargepoints

        rate_ac = Datex2EnergyRate(
            id="adHoc",
            rate_policy="adHoc",
            currencies=["EUR"],
            prices=[
                Datex2EnergyPrice(
                    price_type=Datex2EnergyPrice.PriceType.PRICE_PER_KWH,
                    value=0.39,
                    tax_included=False,
                ),
            ],
        )
        rate_dc = Datex2EnergyRate(
            id="adHoc",
            rate_policy="adHoc",
            currencies=["EUR"],
            prices=[
                Datex2EnergyPrice(
                    price_type=Datex2EnergyPrice.PriceType.PRICE_PER_KWH,
                    value=0.59,
                    tax_included=False,
                ),
            ],
        )

        site_pricings = [
            Datex2SitePricing(
                site_id="site-1",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*1",
                        energy_rates=[rate_ac],
                    ),
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*2",
                        energy_rates=[rate_dc],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings),
        )
        assert Tariff.objects.count() == 2
        tariff_ac = Tariff.objects.get(price_components__price="0.39000000")
        tariff_dc = Tariff.objects.get(price_components__price="0.59000000")
        assert tariff_ac.chargepoints.count() == 1
        assert tariff_dc.chargepoints.count() == 1
        assert cp1 in tariff_ac.chargepoints.all()
        assert cp2 in tariff_dc.chargepoints.all()

    def test_resync_replaces_old_tariffs(
        self, site_with_chargepoints, simple_energy_rate
    ):
        """Re-syncing should replace old tariffs."""
        site, cp1, cp2 = site_with_chargepoints

        site_pricings = [
            Datex2SitePricing(
                site_id="site-1",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*1",
                        energy_rates=[simple_energy_rate],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings),
        )
        assert Tariff.objects.count() == 1
        old_tariff_id = Tariff.objects.first().pk

        # New rate with different price
        new_rate = Datex2EnergyRate(
            id="adHoc",
            rate_policy="adHoc",
            currencies=["EUR"],
            prices=[
                Datex2EnergyPrice(
                    price_type=Datex2EnergyPrice.PriceType.PRICE_PER_KWH,
                    value=0.49,
                    tax_included=False,
                ),
            ],
        )
        site_pricings_2 = [
            Datex2SitePricing(
                site_id="site-1",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="DE*ABC*E0001*1",
                        energy_rates=[new_rate],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings_2),
        )
        assert Tariff.objects.count() == 1
        new_tariff = Tariff.objects.first()
        assert new_tariff.pk != old_tariff_id
        assert float(new_tariff.price_components.first().price) == pytest.approx(0.49)

    def test_unresolved_chargepoint(self, db):
        """Chargepoints not found in DB should be silently skipped."""
        rate = Datex2EnergyRate(
            id="adHoc",
            rate_policy="adHoc",
            currencies=["EUR"],
            prices=[
                Datex2EnergyPrice(
                    price_type=Datex2EnergyPrice.PriceType.PRICE_PER_KWH,
                    value=0.39,
                    tax_included=False,
                ),
            ],
        )
        site_pricings = [
            Datex2SitePricing(
                site_id="nonexistent-site",
                refill_point_pricings=[
                    Datex2RefillPointPricing(
                        refill_point_id="nonexistent-cp",
                        energy_rates=[rate],
                    ),
                ],
            )
        ]

        sync_pricing(
            "test_pricing",
            "test_static",
            _convert_site_pricings(site_pricings),
        )
        # Tariff is still created (it represents the pricing itself)
        assert Tariff.objects.count() == 1
        # But no chargepoints linked
        assert Tariff.objects.first().chargepoints.count() == 0
