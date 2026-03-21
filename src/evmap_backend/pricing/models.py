from django.db import models

from evmap_backend.pricing.fields import DayOfWeekBitField


class Tariff(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["data_source", "id_from_source"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "id_from_source"],
                name="unique_tariff_per_source",
                nulls_distinct=True,
            ),
        ]

    name = models.CharField(max_length=255, blank=True)
    is_adhoc = models.BooleanField(
        default=True,
        help_text="Whether this is the ad-hoc tariff offered by the CPO.",
    )

    data_source = models.CharField(max_length=255, blank=True)
    id_from_source = models.CharField(
        max_length=255, blank=True, null=True, default=None
    )

    currency = models.CharField(
        max_length=3, help_text="ISO 4217 currency code (e.g. EUR, CHF, GBP)."
    )

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    description = models.TextField(blank=True)

    min_price = models.DecimalField(
        max_digits=14,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Minimum total price for a charging session using this tariff.",
    )
    max_price = models.DecimalField(
        max_digits=14,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Maximum total price for a charging session using this tariff.",
    )

    chargepoints = models.ManyToManyField(
        "chargers.Chargepoint",
        related_name="tariffs",
        blank=True,
    )

    def __str__(self):
        parts = []
        if self.name:
            parts.append(self.name)
        if self.data_source:
            parts.append(f"[{self.data_source}]")
        if self.id_from_source:
            parts.append(f"({self.id_from_source})")
        return " ".join(parts) if parts else f"Tariff #{self.pk}"


class PriceComponent(models.Model):
    class PriceComponentType(models.TextChoices):
        ENERGY = "ENERGY", "Energy (per kWh)"
        FLAT = "FLAT", "Flat fee (per session)"
        TIME = "TIME", "Time (per minute, charging)"
        PARKING_TIME = "PARKING_TIME", "Parking time (per minute, not charging)"

    tariff = models.ForeignKey(
        Tariff, on_delete=models.CASCADE, related_name="price_components"
    )
    type = models.CharField(max_length=20, choices=PriceComponentType)
    price = models.DecimalField(
        max_digits=14,
        decimal_places=8,
        help_text=(
            "Price per unit (excl. or incl. tax depending on tax_included). "
            "Units: ENERGY in per kWh, TIME/PARKING_TIME in per minute, FLAT per session."
        ),
    )
    tax_included = models.BooleanField(help_text="Whether the price includes tax.")
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Tax rate as a percentage (e.g. 19.00 for 19% VAT).",
    )
    step_size = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Minimum granularity of billing. "
            "For ENERGY: in Wh. For TIME/PARKING_TIME: in seconds. For FLAT: must be 1."
        ),
    )

    # Price caps per component
    min_price = models.DecimalField(
        max_digits=14,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Minimum price for this component per session.",
    )
    max_price = models.DecimalField(
        max_digits=14,
        decimal_places=8,
        null=True,
        blank=True,
        help_text="Maximum price for this component per session.",
    )

    # Restrictions
    day_of_week = DayOfWeekBitField()

    time_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time of day this component applies (inclusive).",
    )
    time_end = models.TimeField(
        null=True,
        blank=True,
        help_text="End time of day this component applies (exclusive).",
    )

    min_power = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum charging power in watts for this component to apply.",
    )
    max_power = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum charging power in watts for this component to apply.",
    )

    min_duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Minimum duration in seconds for this component to apply.",
    )
    max_duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum duration in seconds for this component to apply.",
    )

    _UNIT_LABELS = {
        PriceComponentType.ENERGY: "/kWh",
        PriceComponentType.FLAT: " flat",
        PriceComponentType.TIME: "/min",
        PriceComponentType.PARKING_TIME: "/min parking",
    }

    def __str__(self):
        from decimal import ROUND_HALF_UP, Decimal

        gross = self.price
        if not self.tax_included and self.tax_rate:
            gross = self.price * (1 + self.tax_rate / 100)
        gross = gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        unit = self._UNIT_LABELS.get(self.type, "")
        currency = self.tariff.currency if self.tariff_id else ""
        parts = [f"{gross} {currency}{unit}"]
        if self.min_duration:
            parts.append(f"after {self.min_duration // 60} min")
        return " ".join(parts)


class NetworkTariffAssignment(models.Model):
    """Assign a tariff to all chargepoints of a network, optionally filtered by AC/DC or power."""

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tariff"],
                name="unique_network_assignment_per_tariff",
            ),
        ]

    tariff = models.OneToOneField(
        Tariff, on_delete=models.CASCADE, related_name="network_assignment"
    )
    network = models.ForeignKey(
        "chargers.Network",
        on_delete=models.CASCADE,
        related_name="tariff_assignments",
    )
    is_dc = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        help_text="Filter: True = DC only, False = AC only, None = all.",
    )
    min_power = models.FloatField(
        null=True,
        blank=True,
        help_text="Filter: minimum connector power in watts.",
    )
    max_power = models.FloatField(
        null=True,
        blank=True,
        help_text="Filter: maximum connector power in watts.",
    )

    def __str__(self):
        parts = [f"{self.tariff} → {self.network}"]
        if self.is_dc is not None:
            parts.append("DC" if self.is_dc else "AC")
        if self.min_power is not None or self.max_power is not None:
            power_range = f"{self.min_power or '?'}–{self.max_power or '?'} W"
            parts.append(power_range)
        return " ".join(parts)
