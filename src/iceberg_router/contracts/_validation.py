"""Shared standard-library validation for portable contract values."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


_DECIMAL_PATTERN = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_PROBABILITY_PATTERN = re.compile(r"(?:0(?:\.[0-9]+)?|1(?:\.0+)?)\Z")


def require_text(value: object, field: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value or len(value) > maximum:
        raise ValueError(f"{field} must contain 1 to {maximum} characters")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError(f"{field} must not contain control characters")
    return value


def require_decimal_text(value: object, field: str) -> str:
    text = require_text(value, field)
    if not _DECIMAL_PATTERN.fullmatch(text):
        raise ValueError(f"{field} must be a plain base-10 decimal string")
    return text


def require_probability_text(value: object, field: str) -> str:
    text = require_text(value, field)
    if not _PROBABILITY_PATTERN.fullmatch(text):
        raise ValueError(f"{field} must be a decimal string between 0 and 1")
    return text


def require_utc_timestamp(value: object, field: str = "timestamp") -> str:
    text = require_text(value, field)
    if not text.endswith("Z"):
        raise ValueError(f"{field} must use UTC with a trailing Z")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} must be an RFC 3339 timestamp") from error
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field} must use UTC")
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if canonical != text:
        raise ValueError(f"{field} must use canonical RFC 3339 formatting")
    return text


def parse_utc_timestamp(value: object, field: str = "timestamp") -> datetime:
    text = require_utc_timestamp(value, field)
    return datetime.fromisoformat(text[:-1] + "+00:00")


def require_mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{field} must be an object with string keys")
    return value


def require_exact_keys(value: dict[str, Any], field: str, keys: set[str]) -> None:
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise ValueError(f"{field} has missing keys {missing} and extra keys {extra}")
