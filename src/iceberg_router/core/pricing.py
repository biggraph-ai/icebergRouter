"""Exact fixed-unit tariff and upper-liability calculation."""

from __future__ import annotations

from dataclasses import dataclass

from iceberg_router.contracts._validation import require_text
from iceberg_router.contracts.money import MAX_NANODOLLARS, Nanodollars
from iceberg_router.contracts.options import OperationLimits
from iceberg_router.contracts.resources import ResourceIdentity


@dataclass(frozen=True, slots=True)
class Tariff:
    version: str
    resource: ResourceIdentity
    input_token_nanos: Nanodollars
    output_token_nanos: Nanodollars
    per_request_nanos: Nanodollars
    max_non_token_nanos: Nanodollars
    rounding_increment_nanos: Nanodollars

    def __post_init__(self) -> None:
        require_text(self.version, "version", maximum=128)
        if not isinstance(self.resource, ResourceIdentity):
            raise TypeError("resource must be ResourceIdentity")
        for field in (
            "input_token_nanos", "output_token_nanos", "per_request_nanos",
            "max_non_token_nanos", "rounding_increment_nanos",
        ):
            if not isinstance(getattr(self, field), Nanodollars):
                raise TypeError(f"{field} must be Nanodollars")
        if self.rounding_increment_nanos.value < 1:
            raise ValueError("rounding increment must be positive")


def calculate_attempt_bound(
    tariff: Tariff,
    limits: OperationLimits,
    *,
    calculator_version: str,
) -> Nanodollars:
    """Calculate one-attempt liability from enforced caps with checked arithmetic."""

    require_text(calculator_version, "calculator_version", maximum=128)
    raw = (
        tariff.input_token_nanos.value * limits.max_input_tokens
        + tariff.output_token_nanos.value * limits.max_output_tokens
        + tariff.per_request_nanos.value
        + tariff.max_non_token_nanos.value
    )
    increment = tariff.rounding_increment_nanos.value
    rounded = ((raw + increment - 1) // increment) * increment
    if rounded > MAX_NANODOLLARS:
        raise ValueError("tariff bound exceeds supported money range")
    return Nanodollars(rounded)
