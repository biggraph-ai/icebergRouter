"""Deterministic fixed-option control policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from iceberg_router.contracts.decisions import DecisionRecord, Probability
from iceberg_router.contracts.identifiers import (
    OptionId,
    PolicyVersion,
)
from iceberg_router.contracts.routing import PolicyRequest


class PolicyConfigurationError(ValueError):
    """A control policy configuration is invalid."""


def _decision(
    request: PolicyRequest,
    policy_version: PolicyVersion,
    selected: OptionId | None,
    probability: Decimal,
    deferral_reason: str | None = None,
) -> DecisionRecord:
    return DecisionRecord(
        decision_id=request.decision_id,
        request_id=request.request_id,
        workload_id=request.workload_id,
        policy_version=policy_version,
        snapshot_version=request.snapshot_version,
        candidates=request.candidates,
        selected_option_id=selected,
        selection_probability=Probability(probability),
        randomization_seed=request.randomization_seed,
        deferral_reason=deferral_reason,
    )


@dataclass(frozen=True, slots=True)
class FixedPolicy:
    option_id: OptionId
    policy_version: PolicyVersion

    def __post_init__(self) -> None:
        if not isinstance(self.option_id, OptionId):
            raise TypeError("option_id must be OptionId")
        if not isinstance(self.policy_version, PolicyVersion):
            raise TypeError("policy_version must be PolicyVersion")

    def select(self, request: PolicyRequest) -> DecisionRecord:
        if not isinstance(request, PolicyRequest):
            raise TypeError("request must be PolicyRequest")
        candidate = next(
            (item for item in request.candidates if item.option_id == self.option_id), None
        )
        if candidate is None:
            return _decision(
                request, self.policy_version, None, Decimal(1), "fixed_option_missing"
            )
        if not candidate.eligible:
            return _decision(
                request, self.policy_version, None, Decimal(1), "fixed_option_ineligible"
            )
        return _decision(request, self.policy_version, self.option_id, Decimal(1))
