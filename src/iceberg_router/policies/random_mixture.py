"""Exact seeded mixture controls with explicit eligibility semantics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import reduce
import hashlib
from math import gcd
from types import MappingProxyType
from typing import Mapping

from iceberg_router.contracts.decisions import DecisionRecord, Probability
from iceberg_router.contracts.identifiers import OptionId, PolicyVersion

from .fixed import PolicyConfigurationError, PolicyRequest, _decision

_HASH_MODULUS = 1 << 256
_MAX_REJECTION_DRAWS = 1024


def _decimal_coefficient(value: Decimal) -> tuple[int, int]:
    sign, digits, exponent = value.as_tuple()
    if sign:
        raise PolicyConfigurationError("probabilities must be nonnegative")
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    if exponent >= 0:
        return coefficient * (10**exponent), 0
    return coefficient, -exponent


def _integer_distribution(
    probabilities: Mapping[OptionId, Probability],
) -> tuple[tuple[OptionId, int], ...]:
    """Return reduced exact weights without Decimal arithmetic or context rounding."""

    coefficients = {
        option_id: _decimal_coefficient(probability.value)
        for option_id, probability in probabilities.items()
    }
    maximum_scale = max(scale for _, scale in coefficients.values())
    weights = tuple(
        (
            option_id,
            coefficient * (10 ** (maximum_scale - scale)),
        )
        for option_id, (coefficient, scale) in sorted(
            coefficients.items(), key=lambda item: item[0].value
        )
    )
    denominator = 10**maximum_scale
    if sum(weight for _, weight in weights) != denominator:
        raise PolicyConfigurationError("probabilities must sum exactly to 1")
    common = reduce(gcd, (weight for _, weight in weights), denominator)
    reduced = tuple((option_id, weight // common) for option_id, weight in weights)
    reduced_total = denominator // common
    if reduced_total > _HASH_MODULUS:
        raise PolicyConfigurationError(
            "reduced probability denominator exceeds the 256-bit sampler"
        )
    return reduced


def _uniform_index(seed: str, upper_bound: int) -> int:
    """Return an unbiased deterministic integer with a defensive iteration bound."""

    if isinstance(upper_bound, bool) or not isinstance(upper_bound, int):
        raise TypeError("upper_bound must be an integer")
    if upper_bound < 1 or upper_bound > _HASH_MODULUS:
        raise PolicyConfigurationError("sampler upper bound is unsupported")
    limit = _HASH_MODULUS - _HASH_MODULUS % upper_bound
    for counter in range(_MAX_REJECTION_DRAWS):
        digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        value = int.from_bytes(digest, "big")
        if value < limit:
            return value % upper_bound
    raise RuntimeError("bounded rejection sampler exhausted")


def _exact_probability(weight: int, total: int) -> Decimal:
    """Build an exact terminating Decimal from a reduced base-10-derived ratio."""

    common = gcd(weight, total)
    weight //= common
    total //= common
    twos = fives = 0
    remainder = total
    while remainder % 2 == 0:
        remainder //= 2
        twos += 1
    while remainder % 5 == 0:
        remainder //= 5
        fives += 1
    if remainder != 1:
        raise PolicyConfigurationError("probability denominator is not terminating")
    scale = max(twos, fives)
    coefficient = weight * (2 ** (scale - twos)) * (5 ** (scale - fives))
    digits = tuple(int(character) for character in str(coefficient))
    return Decimal((0, digits, -scale))


def _sample(seed: str, distribution: tuple[tuple[OptionId, int], ...]) -> tuple[OptionId, int, int]:
    total = sum(weight for _, weight in distribution)
    draw = _uniform_index(seed, total)
    cumulative = 0
    for option_id, weight in distribution:
        cumulative += weight
        if draw < cumulative:
            return option_id, weight, total
    raise RuntimeError("exact distribution did not cover sampled index")


@dataclass(frozen=True, slots=True)
class DrawThenDeferMixturePolicy:
    """Baseline: draw from all options, then defer if the draw is ineligible."""

    probabilities: Mapping[OptionId, Probability]
    policy_version: PolicyVersion

    def __post_init__(self) -> None:
        _validate_configuration(self)

    def select(self, request: PolicyRequest) -> DecisionRecord:
        candidates = _candidate_map(request, self.probabilities)
        distribution = _integer_distribution(self.probabilities)
        sampled, weight, total = _sample(request.randomization_seed, distribution)
        if candidates[sampled].eligible:
            return _decision(
                request, self.policy_version, sampled, _exact_probability(weight, total)
            )
        deferred_weight = sum(
            item_weight
            for option_id, item_weight in distribution
            if not candidates[option_id].eligible
        )
        return _decision(
            request,
            self.policy_version,
            None,
            _exact_probability(deferred_weight, total),
            "sampled_option_ineligible",
        )


@dataclass(frozen=True, slots=True)
class FeasibleMixturePolicy:
    """Control: renormalize exact configured weights over eligible options."""

    probabilities: Mapping[OptionId, Probability]
    policy_version: PolicyVersion

    def __post_init__(self) -> None:
        _validate_configuration(self)

    def select(self, request: PolicyRequest) -> DecisionRecord:
        candidates = _candidate_map(request, self.probabilities)
        eligible = tuple(
            item
            for item in _integer_distribution(self.probabilities)
            if candidates[item[0]].eligible
        )
        if not eligible:
            return _decision(
                request, self.policy_version, None, Decimal(1), "no_eligible_mixture_option"
            )
        eligible_total = sum(weight for _, weight in eligible)
        for _, weight in eligible:
            _exact_probability(weight, eligible_total)
        sampled, weight, total = _sample(request.randomization_seed, eligible)
        return _decision(
            request, self.policy_version, sampled, _exact_probability(weight, total)
        )


def _validate_configuration(policy) -> None:
    if not isinstance(policy.probabilities, Mapping):
        raise TypeError("probabilities must be a mapping")
    if not policy.probabilities:
        raise PolicyConfigurationError("probabilities must not be empty")
    if any(not isinstance(key, OptionId) for key in policy.probabilities):
        raise TypeError("probability keys must be OptionId values")
    if any(not isinstance(value, Probability) for value in policy.probabilities.values()):
        raise TypeError("probability values must be Probability values")
    if not isinstance(policy.policy_version, PolicyVersion):
        raise TypeError("policy_version must be PolicyVersion")
    if any(value.value == 0 for value in policy.probabilities.values()):
        raise PolicyConfigurationError("configured probabilities must be positive")
    _integer_distribution(policy.probabilities)
    object.__setattr__(
        policy, "probabilities", MappingProxyType(dict(policy.probabilities))
    )


def _candidate_map(request, probabilities):
    if not isinstance(request, PolicyRequest):
        raise TypeError("request must be PolicyRequest")
    candidates = {item.option_id: item for item in request.candidates}
    missing = set(probabilities) - set(candidates)
    if missing:
        raise PolicyConfigurationError(
            "mixture options are absent from the candidate snapshot: "
            + ", ".join(sorted(item.value for item in missing))
        )
    return candidates


# Reviewed compatibility alias; the explicit baseline name is preferred.
RandomMixturePolicy = DrawThenDeferMixturePolicy
