"""Exact, checked invoice-accounting money values."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final


MAX_NANODOLLARS: Final[int] = (1 << 63) - 1
_WIRE_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\Z")


@dataclass(frozen=True, order=True, slots=True)
class Nanodollars:
    """A non-negative, signed-64-bit-compatible count of nanodollars.

    Portable JSON represents this value as a canonical decimal string.  The class
    intentionally rejects floats, booleans, negative amounts, and unchecked range
    growth.
    """

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("nanodollars must be an integer")
        if not 0 <= self.value <= MAX_NANODOLLARS:
            raise ValueError(f"nanodollars must be between 0 and {MAX_NANODOLLARS}")

    @classmethod
    def from_json(cls, value: object) -> Nanodollars:
        if not isinstance(value, str):
            raise TypeError("nanodollars JSON value must be a decimal string")
        if not _WIRE_PATTERN.fullmatch(value):
            raise ValueError("nanodollars JSON value must be a canonical decimal string")
        return cls(int(value))

    def to_json(self) -> str:
        return str(self.value)

    def __add__(self, other: object) -> Nanodollars:
        if not isinstance(other, Nanodollars):
            return NotImplemented
        return Nanodollars(self.value + other.value)

    def __sub__(self, other: object) -> Nanodollars:
        if not isinstance(other, Nanodollars):
            return NotImplemented
        return Nanodollars(self.value - other.value)


ZERO_NANODOLLARS: Final[Nanodollars] = Nanodollars(0)


def checked_sum(values: tuple[Nanodollars, ...]) -> Nanodollars:
    total = ZERO_NANODOLLARS
    for value in values:
        if not isinstance(value, Nanodollars):
            raise TypeError("checked_sum accepts only Nanodollars")
        total = total + value
    return total
