import re
from enum import Enum, StrEnum
from functools import partial
from typing import Optional

import opening_hours
from django.core.exceptions import ValidationError
from django.db import models
from django_countries.data import COUNTRIES


def validate_opening_hours(value: str):
    if not opening_hours.validate(value):
        raise ValidationError(f"Invalid opening hours syntax: {value}")


class OpeningHoursField(models.TextField):
    def __init__(self, *args, **kwargs):
        self.default_validators = [validate_opening_hours]
        super().__init__(*args, **kwargs)


def normalize_evseid(value: str) -> str:
    """
    Normalize EVSEID:
    - Uppercase
    - Remove separators (*, -, space)
    """
    return re.sub(r"[*\-\s]", "", value).upper()


def format_evseid(value: str) -> str:
    """
    Format EVSEID for display by inserting asterisks after country code and operator ID.
    Example stored: DEABCE12345
    Example display: DE ABC E12345
    """
    validate_evseid(value)
    return f"{value[:2]}*{value[2:5]}*{value[5:]}"


class EVSEIDType(StrEnum):
    EVSE = "E"  # single EVSE (chargepoint) - required
    STATION = "S"  # charging station (site) - optional
    POOL = "P"  # pool of charging stations - optional


def validate_evseid(value: str, evseid_type: Optional[EVSEIDType] = None):
    """
    Validate EVSEID in normalized (separator-free) form.
    Expected: 2 letters country, 3 operator chars, type ('E', 'S', or 'P'), 1–31 chars.
    Example stored: DEABCE12345
    """
    if evseid_type is None:
        type_regex = r"[ESP]"
    else:
        type_regex = evseid_type.value
    pattern = r"^[A-Z]{2}[A-Z0-9]{3}" + type_regex + r"[A-Z0-9]{1,31}$"
    if not re.match(pattern, value):
        raise ValidationError(
            f"{value} is not a valid EVSEID"
            + (f" for type {evseid_type.name}" if evseid_type else "")
            + "."
        )
    validate_alpha2_country_code(value[:2])


def validate_evse_operator_id(value: str):
    """
    Validate EVSE Operator ID in normalized (separator-free) form.
    Expected: 2 letters country, 3 operator chars.
    Example stored: DEABC
    """
    pattern = r"^[A-Z]{2}[A-Z0-9]{3}$"
    if not re.match(pattern, value):
        raise ValidationError(f"{value} is not a valid EVSE Operator ID.")
    validate_alpha2_country_code(value[:2])


def validate_alpha2_country_code(country_code: str):
    """
    Validate that the given country code is a valid ISO 3166-1 alpha-2 country code.

    :param country_code: The country code to validate.
    :raises ValidationError: If the country code is not valid.
    """
    if not country_code in COUNTRIES:
        raise ValidationError(f"{country_code} is not a valid country code.")


class EVSEIDField(models.CharField):
    description = "EVSE Identifier (normalized without separators)"

    def __init__(
        self, max_length=37, evseid_type: Optional[EVSEIDType] = None, *args, **kwargs
    ):
        self.default_validators = [partial(validate_evseid, evseid_type=evseid_type)]
        super().__init__(*args, max_length=max_length, **kwargs)

    def get_prep_value(self, value):
        if value is None:
            return value
        return normalize_evseid(value)


class EVSEOperatorIDField(models.CharField):
    description = "EVSE Operator ID (normalized without separators)"

    def __init__(self, max_length=5, *args, **kwargs):
        self.default_validators = [validate_evse_operator_id]
        super().__init__(*args, max_length=max_length, **kwargs)

    def get_prep_value(self, value):
        if value is None:
            return value
        return normalize_evseid(value)
