"""Exact offline coverage and observation accounting for Increment 9."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Sequence

from iceberg_router.contracts.feedback import (
    CheckerResult,
    ObjectiveResult,
    UserVote,
)
from iceberg_router.contracts.identifiers import DecisionId, OptionId, RequestId
from iceberg_router.contracts.money import Nanodollars, checked_sum


class EvaluationError(ValueError):
    """Evaluation records cannot be compared without changing their meaning."""


class EvidenceKind(str, Enum):
    EXECUTED = "executed"
    SYNTHETIC = "synthetic"


class ServiceOutcome(str, Enum):
    SERVED = "served"
    DEFERRED = "deferred"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class ExactRate:
    """A rate retained as an exact numerator/denominator pair."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        for value, field in (
            (self.numerator, "numerator"),
            (self.denominator, "denominator"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")
        if self.denominator <= 0:
            raise ValueError("denominator must be positive")
        if not 0 <= self.numerator <= self.denominator:
            raise ValueError("numerator must be between zero and denominator")

    def to_json(self) -> dict[str, int]:
        return {"numerator": self.numerator, "denominator": self.denominator}


@dataclass(frozen=True, slots=True)
class EvaluationObservation:
    """One original-workload row; absence of feedback is represented explicitly."""

    request_id: RequestId
    decision_id: DecisionId
    evidence_kind: EvidenceKind
    service_outcome: ServiceOutcome
    selected_option_id: OptionId | None
    known_cost: Nanodollars
    unknown_cost_attempts: int
    user_vote: UserVote = UserVote.MISSING
    objective_result: ObjectiveResult = ObjectiveResult.UNKNOWN
    checker_result: CheckerResult = CheckerResult.NOT_RUN

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.request_id, RequestId, "request_id"),
            (self.decision_id, DecisionId, "decision_id"),
            (self.known_cost, Nanodollars, "known_cost"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field} must be {expected.__name__}")
        if not isinstance(self.evidence_kind, EvidenceKind):
            raise TypeError("evidence_kind must be EvidenceKind")
        if not isinstance(self.service_outcome, ServiceOutcome):
            raise TypeError("service_outcome must be ServiceOutcome")
        if self.selected_option_id is not None and not isinstance(
            self.selected_option_id, OptionId
        ):
            raise TypeError("selected_option_id must be OptionId or None")
        if isinstance(self.unknown_cost_attempts, bool) or not isinstance(
            self.unknown_cost_attempts, int
        ):
            raise TypeError("unknown_cost_attempts must be an integer")
        if self.unknown_cost_attempts < 0:
            raise ValueError("unknown_cost_attempts must be non-negative")
        if not isinstance(self.user_vote, UserVote):
            raise TypeError("user_vote must be UserVote")
        if not isinstance(self.objective_result, ObjectiveResult):
            raise TypeError("objective_result must be ObjectiveResult")
        if not isinstance(self.checker_result, CheckerResult):
            raise TypeError("checker_result must be CheckerResult")
        if self.service_outcome is ServiceOutcome.PENDING and self.unknown_cost_attempts == 0:
            raise ValueError("pending service requires at least one unknown-cost attempt")


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    evidence_kind: EvidenceKind
    original_workload_size: int
    service_counts: Mapping[ServiceOutcome, int]
    selection_counts: Mapping[OptionId, int]
    known_cost: Nanodollars
    unknown_cost_attempts: int
    user_vote_counts: Mapping[UserVote, int]
    objective_counts: Mapping[ObjectiveResult, int]
    checker_counts: Mapping[CheckerResult, int]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_kind, EvidenceKind):
            raise TypeError("evidence_kind must be EvidenceKind")
        if isinstance(self.original_workload_size, bool) or not isinstance(
            self.original_workload_size, int
        ):
            raise TypeError("original_workload_size must be an integer")
        if self.original_workload_size <= 0:
            raise ValueError("original_workload_size must be positive")
        if not isinstance(self.known_cost, Nanodollars):
            raise TypeError("known_cost must be Nanodollars")
        if isinstance(self.unknown_cost_attempts, bool) or not isinstance(
            self.unknown_cost_attempts, int
        ):
            raise TypeError("unknown_cost_attempts must be an integer")
        if self.unknown_cost_attempts < 0:
            raise ValueError("unknown_cost_attempts must be non-negative")
        service = self._validated_counts(
            self.service_counts, ServiceOutcome, "service_counts"
        )
        votes = self._validated_counts(self.user_vote_counts, UserVote, "user_vote_counts")
        objectives = self._validated_counts(
            self.objective_counts, ObjectiveResult, "objective_counts"
        )
        checkers = self._validated_counts(
            self.checker_counts, CheckerResult, "checker_counts"
        )
        for counts, field in (
            (service, "service_counts"),
            (votes, "user_vote_counts"),
            (objectives, "objective_counts"),
            (checkers, "checker_counts"),
        ):
            if sum(counts.values()) != self.original_workload_size:
                raise ValueError(f"{field} must account for the original workload")
        if not isinstance(self.selection_counts, Mapping):
            raise TypeError("selection_counts must be a mapping")
        selections = dict(self.selection_counts)
        if any(not isinstance(key, OptionId) for key in selections):
            raise TypeError("selection count keys must be OptionId values")
        self._validate_nonnegative_counts(selections, "selection_counts")
        if sum(selections.values()) > self.original_workload_size:
            raise ValueError("selection counts cannot exceed the original workload")
        object.__setattr__(self, "service_counts", MappingProxyType(service))
        object.__setattr__(self, "selection_counts", MappingProxyType(selections))
        object.__setattr__(self, "user_vote_counts", MappingProxyType(votes))
        object.__setattr__(self, "objective_counts", MappingProxyType(objectives))
        object.__setattr__(self, "checker_counts", MappingProxyType(checkers))

    @staticmethod
    def _validate_nonnegative_counts(counts: Mapping[object, int], field: str) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) for value in counts.values()):
            raise TypeError(f"{field} values must be integers")
        if any(value < 0 for value in counts.values()):
            raise ValueError(f"{field} values must be non-negative")

    @classmethod
    def _validated_counts(cls, counts, enum_type, field):
        if not isinstance(counts, Mapping):
            raise TypeError(f"{field} must be a mapping")
        copied = dict(counts)
        if set(copied) != set(enum_type):
            raise ValueError(f"{field} must contain every {enum_type.__name__} value")
        cls._validate_nonnegative_counts(copied, field)
        return copied

    @property
    def coverage(self) -> ExactRate:
        return ExactRate(
            self.service_counts[ServiceOutcome.SERVED], self.original_workload_size
        )

    @property
    def deferral_rate(self) -> ExactRate:
        return ExactRate(
            self.service_counts[ServiceOutcome.DEFERRED], self.original_workload_size
        )

    def to_json(self) -> dict[str, object]:
        return {
            "evidenceKind": self.evidence_kind.value,
            "originalWorkloadSize": self.original_workload_size,
            "serviceCounts": {
                key.value: self.service_counts[key] for key in ServiceOutcome
            },
            "selectionCounts": {
                key.value: value
                for key, value in sorted(
                    self.selection_counts.items(), key=lambda item: item[0].value
                )
            },
            "knownCostNanos": self.known_cost.to_json(),
            "unknownCostAttempts": self.unknown_cost_attempts,
            "userVoteCounts": {key.value: self.user_vote_counts[key] for key in UserVote},
            "objectiveCounts": {
                key.value: self.objective_counts[key] for key in ObjectiveResult
            },
            "checkerCounts": {
                key.value: self.checker_counts[key] for key in CheckerResult
            },
            "coverage": self.coverage.to_json(),
            "deferralRate": self.deferral_rate.to_json(),
        }


def _counts(enum_type, observations: Sequence[EvaluationObservation], attribute: str):
    return {
        value: sum(getattr(item, attribute) is value for item in observations)
        for value in enum_type
    }


def summarize(observations: Sequence[EvaluationObservation]) -> EvaluationSummary:
    """Aggregate a homogeneous evidence table without dropping deferred rows."""
    if not isinstance(observations, Sequence) or not observations:
        raise EvaluationError("observations must be a non-empty sequence")
    if any(not isinstance(item, EvaluationObservation) for item in observations):
        raise TypeError("observations must contain EvaluationObservation values")
    request_ids = [item.request_id for item in observations]
    decision_ids = [item.decision_id for item in observations]
    if len(set(request_ids)) != len(request_ids):
        raise EvaluationError("request IDs must be unique in the workload")
    if len(set(decision_ids)) != len(decision_ids):
        raise EvaluationError("decision IDs must be unique in the workload")
    evidence = {item.evidence_kind for item in observations}
    if len(evidence) != 1:
        raise EvaluationError("executed and synthetic evidence cannot be combined")
    selection_counts: dict[OptionId, int] = {}
    for item in observations:
        if item.selected_option_id is not None:
            selection_counts[item.selected_option_id] = (
                selection_counts.get(item.selected_option_id, 0) + 1
            )
    return EvaluationSummary(
        evidence_kind=next(iter(evidence)),
        original_workload_size=len(observations),
        service_counts=_counts(ServiceOutcome, observations, "service_outcome"),
        selection_counts=selection_counts,
        known_cost=checked_sum(item.known_cost for item in observations),
        unknown_cost_attempts=sum(item.unknown_cost_attempts for item in observations),
        user_vote_counts=_counts(UserVote, observations, "user_vote"),
        objective_counts=_counts(ObjectiveResult, observations, "objective_result"),
        checker_counts=_counts(CheckerResult, observations, "checker_result"),
    )


__all__ = (
    "EvaluationError",
    "EvaluationObservation",
    "EvaluationSummary",
    "EvidenceKind",
    "ExactRate",
    "ServiceOutcome",
    "summarize",
)
