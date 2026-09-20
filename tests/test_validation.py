import pytest

from core.validation import ValidationError, validate_player_id


@pytest.mark.parametrize("value,expected", [("2002042838", "2002042838"), ("  00123\t", "00123"), ("0", "0")])
def test_valid(value, expected):
    assert validate_player_id(value) == expected


@pytest.mark.parametrize(
    "value", ["", " ", "12a", "1/2", "../123", "1 2", "1\n2", "-1", "1.2", "１２３", "١٢٣", None, "1" * 252]
)
def test_invalid(value):
    with pytest.raises(ValidationError):
        validate_player_id(value)
