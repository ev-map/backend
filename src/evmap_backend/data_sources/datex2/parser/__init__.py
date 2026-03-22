import datetime
import enum
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.utils import timezone

from evmap_backend.chargers.fields import EVSEIDType, normalize_evseid, validate_evseid
from evmap_backend.chargers.models import Chargepoint, ChargingSite, Connector, Network
from evmap_backend.countries.models import Country
from evmap_backend.helpers.database import none_to_blank
from evmap_backend.pricing.models import PriceComponent, Tariff
from evmap_backend.realtime.models import RealtimeStatus

logger = logging.getLogger(__name__)


@dataclass
class Datex2MultilingualString:
    values: Dict[str, str]

    def first(self) -> Optional[str]:
        return next(iter(self.values.values())) if len(self.values) > 0 else None


@dataclass
class Datex2Connector:
    class ConnectorType(enum.StrEnum):
        CHADEMO = "chademo"
        CEE3 = "cee3"
        CEE5 = "cee5"
        YAZAKI = "yazaki"
        DOMESTIC = "domestic"
        DOMESTIC_A = "domesticA"
        DOMESTIC_B = "domesticB"
        DOMESTIC_C = "domesticC"
        DOMESTIC_D = "domesticD"
        DOMESTIC_E = "domesticE"
        DOMESTIC_F = "domesticF"
        DOMESTIC_G = "domesticG"
        DOMESTIC_H = "domesticH"
        DOMESTIC_I = "domesticI"
        DOMESTIC_J = "domesticJ"
        DOMESTIC_K = "domesticK"
        DOMESTIC_L = "domesticL"
        DOMESTIC_M = "domesticM"
        DOMESTIC_N = "domesticN"
        DOMESTIC_O = "domesticO"
        IEC60309_2_SINGLE_16 = "iec60309x2single16"
        IEC60309_2_THREE_16 = "iec60309x2three16"
        IEC60309_2_THREE_32 = "iec60309x2three32"
        IEC60309_2_THREE_64 = "iec60309x2three64"
        TYPE_1 = "iec62196T1"
        CCS_TYPE_1 = "iec62196T1COMBO"
        TYPE_2 = "iec62196T2"
        CCS_TYPE_2 = "iec62196T2COMBO"
        TYPE_3A = "iec62196T3A"
        TYPE_3C = "iec62196T3C"
        PANTOGRAPH_BOTTOM_UP = "pantographBottomUp"
        PANTOGRAPH_TOP_DOWN = "pantographTopDown"
        TESLA_CONNECTOR_EUROPE = "teslaConnectorEurope"
        NACS = "teslaConnectorAmerica"
        TESLA_R = "teslaR"
        TESLA_S = "teslaS"
        OTHER = "other"

    class ChargingMode(enum.StrEnum):
        MODE_1_AC_1P = "mode1AC1p"
        MODE_1_AC_3P = "mode1AC3p"
        MODE_2_AC_1P = "mode2AC1p"
        MODE_2_AC_3P = "mode2AC3p"
        MODE_3_AC_3P = "mode3AC3p"
        MODE_4_DC = "mode4DC"
        LEGACY_INDUCTIVE = "legacyInductive"
        CCS = "ccs"
        OTHER = "other"
        UNKNOWN = "unknown"

    connector_type: ConnectorType
    max_power: float
    charging_mode: ChargingMode = None

    def convert(self) -> Connector:
        return Connector(
            connector_type=connector_mapping.get(
                self.connector_type, Connector.ConnectorTypes.OTHER
            ),
            max_power=self.max_power if self.max_power is not None else 0.0,
        )


connector_mapping = {
    Datex2Connector.ConnectorType.CHADEMO: Connector.ConnectorTypes.CHADEMO,
    Datex2Connector.ConnectorType.DOMESTIC_F: Connector.ConnectorTypes.SCHUKO,
    Datex2Connector.ConnectorType.IEC60309_2_SINGLE_16: Connector.ConnectorTypes.CEE_SINGLE_16,
    Datex2Connector.ConnectorType.IEC60309_2_THREE_16: Connector.ConnectorTypes.CEE_THREE_16,
    Datex2Connector.ConnectorType.IEC60309_2_THREE_32: Connector.ConnectorTypes.CEE_THREE_32,
    Datex2Connector.ConnectorType.IEC60309_2_THREE_64: Connector.ConnectorTypes.CEE_THREE_64,
    Datex2Connector.ConnectorType.TYPE_1: Connector.ConnectorTypes.TYPE_1,
    Datex2Connector.ConnectorType.CCS_TYPE_1: Connector.ConnectorTypes.CCS_TYPE_1,
    Datex2Connector.ConnectorType.TYPE_2: Connector.ConnectorTypes.TYPE_2,
    Datex2Connector.ConnectorType.CCS_TYPE_2: Connector.ConnectorTypes.CCS_TYPE_2,
    Datex2Connector.ConnectorType.TYPE_3A: Connector.ConnectorTypes.TYPE_3A,
    Datex2Connector.ConnectorType.TYPE_3C: Connector.ConnectorTypes.TYPE_3C,
    Datex2Connector.ConnectorType.TESLA_CONNECTOR_EUROPE: Connector.ConnectorTypes.TESLA_SUPERCHARGER_EU,
    Datex2Connector.ConnectorType.NACS: Connector.ConnectorTypes.NACS,
    Datex2Connector.ConnectorType.TESLA_R: Connector.ConnectorTypes.TESLA_ROADSTER_HPC,
}


@dataclass
class Datex2RefillPoint:
    id: str
    connectors: List[Datex2Connector]
    external_identifier: str = None
    name: Datex2MultilingualString = None

    def convert(self) -> Chargepoint:
        return Chargepoint(
            id_from_source=self.id,
            evseid=(self.get_evseid()),
            physical_reference=none_to_blank(
                self.name.first() if self.name is not None else None
            ),
        )

    def get_evseid(self) -> str:
        evseid = ""
        try:
            id = normalize_evseid(
                self.external_identifier if self.external_identifier else ""
            )
            validate_evseid(id, EVSEIDType.EVSE)
            evseid = id
        except ValidationError:
            try:
                id = normalize_evseid(self.id)
                validate_evseid(id, EVSEIDType.EVSE)
                evseid = id
            except ValidationError:
                if self.name is not None:
                    try:
                        id = normalize_evseid(self.name.first())
                        validate_evseid(id, EVSEIDType.EVSE)
                        evseid = id
                    except ValidationError:
                        pass
        return evseid


@dataclass
class Datex2EnergyInfrastructureSite:
    id: str
    name: Datex2MultilingualString
    # TODO: operatingHours
    location: Tuple[float, float]

    # address
    street: str
    zipcode: str
    city: str
    country: str

    operator_name: Datex2MultilingualString
    operator_phone: Optional[str]
    refill_points: List[Datex2RefillPoint]
    additional_information: Datex2MultilingualString = None

    def convert(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: Optional[str],
    ) -> Tuple[ChargingSite, List[Tuple[Chargepoint, List[Connector]]]]:
        evseid = self.refill_points[0].get_evseid()
        if evseid != "":
            operator_id = normalize_evseid(evseid)[:5]
            network, created = Network.get_or_create(
                evse_operator_id=operator_id,
                defaults=dict(
                    name=none_to_blank(
                        self.operator_name.first() if self.operator_name else None
                    )
                ),
            )
        else:
            network = None

        site = ChargingSite(
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=(
                license_attribution_link if license_attribution_link is not None else ""
            ),
            id_from_source=self.id,
            name=(
                self.name.first()
                if self.name
                else (
                    self.additional_information.first()
                    if self.additional_information
                    else ""
                )
            ),
            location=Point(*self.location),
            network=network,
            street=self.street if self.street is not None else "",
            zipcode=self.zipcode if self.zipcode is not None else "",
            city=self.city if self.city is not None else "",
            country=(
                self.country
                if self.country is not None
                else Country.get_country_for_point(Point(*self.location)) or ""
            ),
        )
        chargepoints = [
            (rp.convert(), [con.convert() for con in rp.connectors])
            for rp in self.refill_points
        ]
        return site, chargepoints


@dataclass
class Datex2RefillPointStatus:
    class Status(enum.StrEnum):
        AVAILABLE = "available"
        BLOCKED = "blocked"
        CHARGING = "charging"
        FAULTED = "faulted"
        INOPERATIVE = "inoperative"
        OCCUPIED = "occupied"
        OUTOFORDER = "outOfOrder"
        OUTOFSTOCK = "outOfStock"
        PLANNED = "planned"
        REMOVED = "removed"
        RESERVED = "reserved"
        UNAVAILABLE = "unavailable"
        UNKNOWN = "unknown"

    refill_point_id: str
    last_updated: Optional[datetime.datetime]
    status: Status

    def convert(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: Optional[str],
    ) -> RealtimeStatus:
        return RealtimeStatus(
            chargepoint=Chargepoint(id_from_source=self.refill_point_id),
            status=status_map[self.status],
            timestamp=(
                self.last_updated if self.last_updated is not None else timezone.now()
            ),
            data_source=data_source,
            license_attribution=license_attribution,
            license_attribution_link=(
                license_attribution_link if license_attribution_link is not None else ""
            ),
        )


status_map = {
    Datex2RefillPointStatus.Status.AVAILABLE: RealtimeStatus.Status.AVAILABLE,
    Datex2RefillPointStatus.Status.BLOCKED: RealtimeStatus.Status.BLOCKED,
    Datex2RefillPointStatus.Status.CHARGING: RealtimeStatus.Status.CHARGING,
    Datex2RefillPointStatus.Status.FAULTED: RealtimeStatus.Status.OUTOFORDER,
    Datex2RefillPointStatus.Status.INOPERATIVE: RealtimeStatus.Status.INOPERATIVE,
    Datex2RefillPointStatus.Status.OCCUPIED: RealtimeStatus.Status.CHARGING,
    Datex2RefillPointStatus.Status.OUTOFORDER: RealtimeStatus.Status.OUTOFORDER,
    Datex2RefillPointStatus.Status.OUTOFSTOCK: RealtimeStatus.Status.OUTOFORDER,
    Datex2RefillPointStatus.Status.PLANNED: RealtimeStatus.Status.PLANNED,
    Datex2RefillPointStatus.Status.REMOVED: RealtimeStatus.Status.REMOVED,
    Datex2RefillPointStatus.Status.RESERVED: RealtimeStatus.Status.RESERVED,
    Datex2RefillPointStatus.Status.UNAVAILABLE: RealtimeStatus.Status.UNKNOWN,
    Datex2RefillPointStatus.Status.UNKNOWN: RealtimeStatus.Status.UNKNOWN,
}


@dataclass
class Datex2EnergyInfrastructureSiteStatus:
    site_id: str
    refill_point_statuses: List[Datex2RefillPointStatus]

    def convert(
        self,
        data_source: str,
        license_attribution: str,
        license_attribution_link: Optional[str],
    ) -> List[Tuple[str, RealtimeStatus]]:
        return [
            (
                self.site_id,
                rps.convert(data_source, license_attribution, license_attribution_link),
            )
            for rps in self.refill_point_statuses
        ]


@dataclass
class Datex2EnergyPrice:
    """A single price component from a Datex2 energyRate."""

    class PriceType(enum.StrEnum):
        FREE = "free"
        FLAT_RATE = "flatRate"
        PRICE_PER_KWH = "pricePerKWh"
        PRICE_PER_MINUTE = "pricePerMinute"
        BASE_PRICE = "basePrice"
        OTHER = "other"

    price_type: PriceType
    value: float
    tax_included: Optional[bool] = None
    tax_rate: Optional[float] = None
    # timeBasedApplicability: fromMinute means "applies after N minutes"
    from_minute: Optional[int] = None
    to_minute: Optional[int] = None

    def convert(self) -> PriceComponent:
        if (
            self.value == 0
        ):  # ignore zero prices, even if they are not explicitly marked as "free"
            return None

        component_type = _PRICE_TYPE_MAP.get(self.price_type)
        if component_type is None:
            logger.warning(
                f"Unknown Datex2 price type: {self.price_type} ({self.value})"
            )
            return None

        component = PriceComponent(
            type=component_type,
            price=Decimal(str(self.value)),
            tax_included=self.tax_included if self.tax_included is not None else True,
            tax_rate=Decimal(str(self.tax_rate)) if self.tax_rate is not None else None,
            step_size=1,
        )

        # timeBasedApplicability: fromMinute means "applies after N minutes"
        if self.from_minute is not None and self.from_minute > 0:
            component.min_duration = self.from_minute * 60  # convert to seconds
        if self.to_minute is not None and self.to_minute > 0:
            component.max_duration = self.to_minute * 60

        return component


_PRICE_TYPE_MAP = {
    Datex2EnergyPrice.PriceType.PRICE_PER_KWH: PriceComponent.PriceComponentType.ENERGY,
    Datex2EnergyPrice.PriceType.FLAT_RATE: PriceComponent.PriceComponentType.FLAT,
    Datex2EnergyPrice.PriceType.PRICE_PER_MINUTE: PriceComponent.PriceComponentType.TIME,
    Datex2EnergyPrice.PriceType.BASE_PRICE: PriceComponent.PriceComponentType.FLAT,
}


@dataclass
class Datex2EnergyRate:
    """A tariff / energy rate from a Datex2 refill point."""

    id: Optional[str]
    rate_policy: Optional[str]  # e.g. "adHoc"
    currencies: List[str]  # ISO 4217, e.g. ["EUR"]
    prices: List[Datex2EnergyPrice]
    last_updated: Optional[datetime.datetime] = None

    def convert(self, data_source: str) -> Tuple[Tariff, List[PriceComponent]]:
        """Convert to an unsaved Tariff and list of unsaved PriceComponents."""
        currency = self.currencies[0] if self.currencies else "EUR"

        tariff = Tariff(
            data_source=data_source,
            id_from_source=None,  # Datex2 has a tariff ID, but IDs are often not unique (e.g., EnBW), so we ignore them
            is_adhoc=self.rate_policy == "adHoc",
            currency=currency,
        )

        components = [p.convert() for p in self.prices]
        components = [c for c in components if c is not None]

        return tariff, components


@dataclass
class Datex2RefillPointPricing:
    """Pricing data for a single refill point (chargepoint)."""

    refill_point_id: str
    energy_rates: List[Datex2EnergyRate]


@dataclass
class Datex2SitePricing:
    """Pricing data for a single energy infrastructure site."""

    site_id: str
    refill_point_pricings: List[Datex2RefillPointPricing]

    def convert(
        self, data_source: str
    ) -> List[Tuple[str, str, Tariff, List[PriceComponent]]]:
        """
        Convert to a list of (site_id, refill_point_id, Tariff, [PriceComponent]) tuples.

        Each energy rate for each refill point produces one tuple.
        """
        results = []
        for rp_pricing in self.refill_point_pricings:
            for rate in rp_pricing.energy_rates:
                tariff, components = rate.convert(data_source)
                results.append(
                    (self.site_id, rp_pricing.refill_point_id, tariff, components)
                )
        return results


def parse_datetime(text, default_timezone=None):
    dt = datetime.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        if default_timezone is None:
            raise ValueError(
                f"Encountered naive datetime without default timezone: {text}"
            )
        dt = default_timezone.localize(dt)
    return dt
