from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

DAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def day_bit(day_name: str) -> int:
    """Return the bit value for a given day name (e.g. 'monday' -> 1)."""
    return 1 << DAYS[day_name.lower()]


def days_to_bits(*day_names: str) -> int:
    """Convert day names to a combined bitmask. E.g. days_to_bits('monday', 'friday') -> 17."""
    return sum(day_bit(d) for d in day_names)


def bits_to_days(value: int) -> list[str]:
    """Convert a bitmask to a list of day names."""
    if value == 0:
        return []
    day_names = list(DAYS.keys())
    return [day_names[i] for i in range(7) if value & (1 << i)]


class DayOfWeekBitField(models.SmallIntegerField):
    """
    A 7-bit field where each bit represents a day of the week.

    Bit 0 = Monday, Bit 1 = Tuesday, ..., Bit 6 = Sunday.

    Value 0 means "all days / no restriction".
    Value 127 (all bits set) is NOT allowed — use 0 instead.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", 0)
        kwargs.setdefault(
            "help_text", "Bitmask for days of week (0=all days, bit 0=Mon..bit 6=Sun)"
        )
        super().__init__(*args, **kwargs)
        self.validators.extend([MinValueValidator(0), MaxValueValidator(126)])

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get("default") == 0:
            del kwargs["default"]
        if (
            kwargs.get("help_text")
            == "Bitmask for days of week (0=all days, bit 0=Mon..bit 6=Sun)"
        ):
            del kwargs["help_text"]
        return name, path, args, kwargs
