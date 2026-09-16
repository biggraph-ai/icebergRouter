"""Seeded random-assignment control with exactly logged propensities."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from types import MappingProxyType
from typing import Mapping

from iceberg_router.contracts.decisions import DecisionRecord, Probability
from iceberg_router.contracts.identifiers import OptionId, PolicyVersion

from .fixed import PolicyConfigurationError, PolicyRequest, _decision


def _integer_distribution(
    probabilities: Mapping[OptionId, Probability],
) -> tuple[tuple[OptionId, int], ...]:
    maximum_scale = max(
        max(0, -item.value.as_tuple().exponent) for item in probabilities.values()
    )
    if maximum_scale > 256:
        raise PolicyConfigurationError(
            "probabilities may contain at most 256 fractional decimal places"
        )
    denominator = 10**maximum_scale
    distribution = tuple(
        (option_id, int(probability.value * denominator))
        for option_id, probability in sorted(probabilities.items(), key=lambda item: item[0].value)
    )
    if sum(weight for _, weight in distribution) != denominator:
        raise PolicyConfigurationError("probabilities must sum exactly to 1")
    return distribution


def _uniform_index(seed: str, upper_bound: int) -> int:
    """Return an unbiased deterministic integer in ``range(upper_bound)``."""
    modulus = 1 << 256
    limit = modulus - modulus % upper_bound
    counter = 0
    while True:
        digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        value = int.from_bytes(digest, "big")
        if value < limit:
            return value % upper_bound
        counter += 1


@dataclass(frozen=True, slots=True)
class RandomMixturePolicy:
    probabilities: Mapping[OptionId, Probability]
    policy_version: PolicyVersion

    def __post_init__(self) -> None:
        if not isinstance(self.probabilities, Mapping):
            raise TypeError("probabilities must be a mapping")
        if not self.probabilities:
            raise PolicyConfigurationError("probabilities must not be empty")
        if any(not isinstance(key, OptionId) for key in self.probabilities):
            raise TypeError("probability keys must be OptionId values")
        if any(
            not isinstance(value, Probability) for value in self.probabilities.values()
        ):
            raise TypeError("probability values must be Probability values")
        if not isinstance(self.policy_version, PolicyVersion):
            raise TypeError("policy_version must be PolicyVersion")
        if any(value.value == 0 for value in self.probabilities.values()):
            raise PolicyConfigurationError("configured probabilities must be positive")
        _integer_distribution(self.probabilities)
        object.__setattr__(self, "probabilities", MappingProxyType(dict(self.probabilities)))

    def select(self, request: PolicyRequest) -> DecisionRecord:
        if not isinstance(request, PolicyRequest):
            raise TypeError("request must be PolicyRequest")
        candidates = {item.option_id: item for item in request.candidates}
        missing = set(self.probabilities) - set(candidates)
        if missing:
            raise PolicyConfigurationError(
                "mixture options are absent from the candidate snapshot: "
                + ", ".join(sorted(item.value for item in missing))
            )
        distribution = _integer_distribution(self.probabilities)
        total = sum(weight for _, weight in distribution)
        draw = _uniform_index(request.randomization_seed, total)
        cumulative = 0
        sampled: OptionId | None = None
        for option_id, weight in distribution:
            cumulative += weight
            if draw < cumulative:
                sampled = option_id
                break
        assert sampled is not None
        sampled_probability = self.probabilities[sampled].value
        if candidates[sampled].eligible:
            return _decision(
                request, self.policy_version, sampled, sampled_probability
            )
        deferral_probability = sum(
            (
                probability.value
                for option_id, probability in self.probabilities.items()
                if not candidates[option_id].eligible
            ),
            Decimal(0),
        )
        return _decision(
            request,
            self.policy_version,
            None,
            deferral_probability,
            "sampled_option_ineligible",
        )
