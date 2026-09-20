"""Small, auditable estimators for frozen categorical context strata."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from types import MappingProxyType
from typing import Iterable, Mapping

from iceberg_router.contracts.identifiers import OptionId
from iceberg_router.contracts.money import Nanodollars


@dataclass(frozen=True, slots=True)
class OutcomeCostObservation:
    context: str
    option_id: OptionId
    succeeded: bool
    actual_cost: Nanodollars

    def __post_init__(self) -> None:
        if not isinstance(self.context, str) or not self.context:
            raise ValueError("context must be non-empty")
        if not isinstance(self.option_id, OptionId):
            raise TypeError("option_id must be OptionId")
        if not isinstance(self.succeeded, bool):
            raise TypeError("succeeded must be bool")
        if not isinstance(self.actual_cost, Nanodollars):
            raise TypeError("actual_cost must be Nanodollars")


@dataclass(frozen=True, slots=True)
class StratumEstimate:
    observations: int
    successes: int
    success_probability: Decimal
    mean_cost: Nanodollars
    intrinsic_variance: Decimal
    probability_standard_error: Decimal

    def __post_init__(self) -> None:
        if self.observations < 1 or not 0 <= self.successes <= self.observations:
            raise ValueError("estimate counts are invalid")


class FrozenStrataEstimator:
    """Immutable empirical outcome/cost estimates; no calibration labels are hidden."""

    def __init__(self, observations: Iterable[OutcomeCostObservation], *, version: str):
        rows = tuple(observations)
        if not rows:
            raise ValueError("observations must not be empty")
        if not isinstance(version, str) or not version:
            raise ValueError("version must be non-empty")
        grouped: dict[tuple[str, OptionId], list[OutcomeCostObservation]] = {}
        for row in rows:
            if not isinstance(row, OutcomeCostObservation):
                raise TypeError("observations must contain OutcomeCostObservation")
            grouped.setdefault((row.context, row.option_id), []).append(row)
        self.version = version
        self._observations = rows
        self._estimates = MappingProxyType({key: self._estimate(value) for key, value in grouped.items()})

    @staticmethod
    def _estimate(rows: list[OutcomeCostObservation]) -> StratumEstimate:
        n = len(rows)
        successes = sum(row.succeeded for row in rows)
        with localcontext() as context:
            context.prec = 40
            probability = Decimal(successes) / Decimal(n)
            intrinsic = probability * (Decimal(1) - probability)
            standard_error = (intrinsic / Decimal(n)).sqrt()
        # Invoice units remain integral; round the empirical mean upward rather than
        # understating an expected cost used by allocation.
        total_cost = sum(row.actual_cost.value for row in rows)
        mean_cost = Nanodollars((total_cost + n - 1) // n)
        return StratumEstimate(n, successes, probability, mean_cost, intrinsic, standard_error)

    @property
    def estimates(self) -> Mapping[tuple[str, OptionId], StratumEstimate]:
        return self._estimates

    @property
    def observations(self) -> tuple[OutcomeCostObservation, ...]:
        return self._observations

    def estimate(self, context: str, option_id: OptionId) -> StratumEstimate:
        try:
            return self._estimates[(context, option_id)]
        except KeyError as error:
            raise KeyError(f"unobserved stratum: {context}/{option_id.value}") from error

    def updated(self, additions: Iterable[OutcomeCostObservation], *, version: str) -> "FrozenStrataEstimator":
        return FrozenStrataEstimator((*self._observations, *tuple(additions)), version=version)
