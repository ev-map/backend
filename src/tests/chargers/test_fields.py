import pytest
from django.core.exceptions import ValidationError

from evmap_backend.chargers.fields import (
    EVSEIDType,
    format_evseid,
    normalize_evseid,
    validate_evse_operator_id,
    validate_evseid,
)


def test_validate_evse_operator_id():
    # Valid IDs
    validate_evse_operator_id("DEIOY")
    validate_evse_operator_id("DE8VO")
    validate_evse_operator_id("DE002")

    # Invalid IDs
    with pytest.raises(ValidationError):
        validate_evse_operator_id("")  # Empty string

    with pytest.raises(ValidationError):
        validate_evse_operator_id("   ")  # Whitespace only

    with pytest.raises(ValidationError):
        validate_evse_operator_id("ZZABC")  # invalid country code

    with pytest.raises(ValidationError):
        validate_evse_operator_id("1AABC")  # country code with digit

    with pytest.raises(ValidationError):
        validate_evse_operator_id("DEOP!")  # only alphanumeric characters are allowed

    with pytest.raises(ValidationError):
        validate_evse_operator_id("DEOPERATOR")  # too long

    with pytest.raises(ValidationError):
        validate_evse_operator_id("DE*IOY")  # non-normalized form


def test_validate_evseid():
    # Valid EVSEIDs
    validate_evseid("DEIOYE1234567")
    validate_evseid("DEIOYE1234567", EVSEIDType.EVSE)
    validate_evseid("DEIOYS12345")
    validate_evseid("DEIOYS12345", EVSEIDType.STATION)
    validate_evseid("DEIOYP1234")
    validate_evseid("DEIOYP1234", EVSEIDType.POOL)

    # Invalid EVSEIDs
    with pytest.raises(ValidationError):
        validate_evseid("")  # Empty string

    with pytest.raises(ValidationError):
        validate_evseid("   ")  # Whitespace only

    with pytest.raises(ValidationError):
        validate_evseid("ZZABCE1234567")  # invalid country code

    with pytest.raises(ValidationError):
        validate_evseid("1AABCE1234567")  # country code with digit

    with pytest.raises(ValidationError):
        validate_evseid("DEOP!E1234567")  # only alphanumeric characters in operator ID

    with pytest.raises(ValidationError):
        validate_evseid("DEOPERATORE1234567")  # operator ID too long

    with pytest.raises(ValidationError):
        validate_evseid("DEIOY1234567")  # missing type prefix

    with pytest.raises(ValidationError):
        validate_evseid("DEIOYE1234!67")  # only alphanumeric characters in unique ID


def test_normalize_evseid():
    assert normalize_evseid("deioye1234567") == "DEIOYE1234567"
    assert normalize_evseid("DE*IOY*E1234567") == "DEIOYE1234567"
    assert normalize_evseid("DE*IOY*E12345*67") == "DEIOYE1234567"
    assert normalize_evseid("DE-IOY-E1234567") == "DEIOYE1234567"
    assert normalize_evseid("DE IOY E1234567") == "DEIOYE1234567"
    assert normalize_evseid("  DE*IOY*E1234567  ") == "DEIOYE1234567"
    assert normalize_evseid("DEIOYE1234567") == "DEIOYE1234567"


def test_display_evseid():
    assert format_evseid("DEIOYE1234567") == "DE*IOY*E1234567"
    assert format_evseid("DEIOYS12345") == "DE*IOY*S12345"
    assert format_evseid("DEIOYP1234") == "DE*IOY*P1234"

    with pytest.raises(ValidationError):
        format_evseid("")  # invalid EVSEID
