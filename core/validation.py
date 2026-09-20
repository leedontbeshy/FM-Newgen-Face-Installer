"""Player IDs are filename-safe ASCII digits, never numbers to be rounded."""

import re


class ValidationError(ValueError):
    pass


def validate_player_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("Invalid Player ID. Enter digits only.")
    player_id = value.strip()
    if not re.fullmatch(r"[0-9]+", player_id):
        raise ValidationError("Invalid Player ID. Enter digits only (0–9).")
    # Windows limits a filename component to 255 characters, including '.png'.
    if len(player_id) > 251:
        raise ValidationError("Invalid Player ID. The ID is too long for a filename.")
    return player_id
