import re
from enum import Enum, StrEnum
from functools import partial
from typing import Optional

import opening_hours
from django.core.exceptions import ValidationError
from django.db import models


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
    # TODO: validate that country code is valid


def validate_evse_operator_id(value: str):
    """
    Validate EVSE Operator ID in normalized (separator-free) form.
    Expected: 2 letters country, 3 operator chars.
    Example stored: DEABC
    """
    pattern = r"^[A-Z]{2}[A-Z0-9]{3}$"
    if not re.match(pattern, value):
        raise ValidationError(f"{value} is not a valid EVSE Operator ID.")
    # TODO: validate that country is valid


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
