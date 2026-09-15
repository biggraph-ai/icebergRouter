"""Portable, immutable routing decision values."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from ._validation import (
    require_decimal_text,
    require_exact_keys,
    require_mapping,
    require_probability_text,
    require_text,
)
from .identifiers import (
    DecisionId,
    OptionId,
    PolicyVersion,
    RequestId,
    SnapshotVersion,
    WorkloadId,
)
from .money import Nanodollars


class EstimateState(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CostEstimate:
    state: EstimateState
    estimator_version: str
    amount: Nanodollars | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, EstimateState):
            raise TypeError("state must be an EstimateState")
        require_text(self.estimator_version, "estimator_version", maximum=128)
        if self.state is EstimateState.KNOWN and not isinstance(self.amount, Nanodollars):
            raise ValueError("known cost estimate requires an amount")
        if self.state is EstimateState.UNKNOWN and self.amount is not None:
            raise ValueError("unknown cost estimate cannot carry an amount")

    def to_json(self) -> dict[str, str | None]:
        return {
            "state": self.state.value,
            "estimatorVersion": self.estimator_version,
            "amountNanos": None if self.amount is None else self.amount.to_json(),
        }

    @classmethod
    def from_json(cls, value: object) -> CostEstimate:
        obj = require_mapping(value, "cost estimate")
        require_exact_keys(obj, "cost estimate", {"state", "estimatorVersion", "amountNanos"})
        try:
            state = EstimateState(obj["state"])
        except (TypeError, ValueError) as error:
            raise ValueError("cost estimate state is invalid") from error
        amount_value = obj["amountNanos"]
        amount = None if amount_value is None else Nanodollars.from_json(amount_value)
        return cls(state, require_text(obj["estimatorVersion"], "estimatorVersion", maximum=128), amount)


@dataclass(frozen=True, slots=True)
class Score:
    value: Decimal
    meaning: str
    calibration_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError("score value must be Decimal")
        if not self.value.is_finite():
            raise ValueError("score value must be finite")
        require_text(self.meaning, "score meaning", maximum=128)
        require_text(self.calibration_version, "calibration_version", maximum=128)

    @classmethod
    def from_json(cls, value: object) -> Score:
        obj = require_mapping(value, "score")
        require_exact_keys(obj, "score", {"value", "meaning", "calibrationVersion"})
        text = require_decimal_text(obj["value"], "score value")
        try:
            parsed = Decimal(text)
        except InvalidOperation as error:
            raise ValueError("score must be a valid decimal") from error
        return cls(
            parsed,
            require_text(obj["meaning"], "score meaning", maximum=128),
            require_text(obj["calibrationVersion"], "calibrationVersion", maximum=128),
        )

    def value_to_json(self) -> str:
        if self.value == 0:
            return "0"
        return format(self.value, "f")

    def to_json(self) -> dict[str, str]:
        return {
            "value": self.value_to_json(),
            "meaning": self.meaning,
            "calibrationVersion": self.calibration_version,
        }


@dataclass(frozen=True, slots=True)
class Probability:
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError("probability value must be Decimal")
        if not self.value.is_finite() or not Decimal(0) <= self.value <= Decimal(1):
            raise ValueError("probability must be finite and between 0 and 1")

    @classmethod
    def from_json(cls, value: object) -> Probability:
        return cls(Decimal(require_probability_text(value, "probability")))

    def to_json(self) -> str:
        if self.value == 0:
            return "0"
        if self.value == 1:
            return "1"
        return format(self.value, "f")


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    option_id: OptionId
    eligible: bool
    eligibility_reasons: tuple[str, ...]
    score: Score | None
    expected_cost: CostEstimate
    upper_liability: CostEstimate

    def __post_init__(self) -> None:
        if not isinstance(self.option_id, OptionId):
            raise TypeError("option_id must be OptionId")
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be bool")
        if not isinstance(self.eligibility_reasons, tuple) or not self.eligibility_reasons:
            raise ValueError("eligibility_reasons must be a non-empty tuple")
        for reason in self.eligibility_reasons:
            require_text(reason, "eligibility reason")
        if self.score is not None and not isinstance(self.score, Score):
            raise TypeError("score must be Score or None")
        if not isinstance(self.expected_cost, CostEstimate):
            raise TypeError("expected_cost must be CostEstimate")
        if not isinstance(self.upper_liability, CostEstimate):
            raise TypeError("upper_liability must be CostEstimate")

    def to_json(self) -> dict[str, Any]:
        return {
            "optionId": self.option_id.to_json(),
            "eligible": self.eligible,
            "eligibilityReasons": list(self.eligibility_reasons),
            "score": None if self.score is None else self.score.to_json(),
            "expectedCost": self.expected_cost.to_json(),
            "upperLiability": self.upper_liability.to_json(),
        }

    @classmethod
    def from_json(cls, value: object) -> CandidateDecision:
        obj = require_mapping(value, "candidate decision")
        require_exact_keys(
            obj,
            "candidate decision",
            {
                "optionId",
                "eligible",
                "eligibilityReasons",
                "score",
                "expectedCost",
                "upperLiability",
            },
        )
        if not isinstance(obj["eligible"], bool):
            raise TypeError("eligible must be bool")
        reasons = obj["eligibilityReasons"]
        if not isinstance(reasons, list):
            raise TypeError("eligibilityReasons must be an array")
        score = obj["score"]
        return cls(
            option_id=OptionId.from_json(obj["optionId"]),
            eligible=obj["eligible"],
            eligibility_reasons=tuple(reasons),
            score=None if score is None else Score.from_json(score),
            expected_cost=CostEstimate.from_json(obj["expectedCost"]),
            upper_liability=CostEstimate.from_json(obj["upperLiability"]),
        )


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decision_id: DecisionId
    request_id: RequestId
    workload_id: WorkloadId
    policy_version: PolicyVersion
    snapshot_version: SnapshotVersion
    candidates: tuple[CandidateDecision, ...]
    selected_option_id: OptionId | None
    selection_probability: Probability
    randomization_seed: str
    deferral_reason: str | None = None

    def __post_init__(self) -> None:
        typed_fields = (
            (self.decision_id, DecisionId, "decision_id"),
            (self.request_id, RequestId, "request_id"),
            (self.workload_id, WorkloadId, "workload_id"),
            (self.policy_version, PolicyVersion, "policy_version"),
            (self.snapshot_version, SnapshotVersion, "snapshot_version"),
        )
        for value, expected, name in typed_fields:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        if not isinstance(self.candidates, tuple) or not self.candidates:
            raise ValueError("candidates must be a non-empty tuple")
        if any(not isinstance(candidate, CandidateDecision) for candidate in self.candidates):
            raise TypeError("candidates must contain CandidateDecision values")
        option_ids = [candidate.option_id for candidate in self.candidates]
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("candidate option IDs must be unique")
        if not isinstance(self.selection_probability, Probability):
            raise TypeError("selection_probability must be Probability")
        require_text(self.randomization_seed, "randomization_seed", maximum=256)

        if self.selected_option_id is None:
            require_text(self.deferral_reason, "deferral_reason")
        else:
            if not isinstance(self.selected_option_id, OptionId):
                raise TypeError("selected_option_id must be OptionId or None")
            selected = next(
                (candidate for candidate in self.candidates if candidate.option_id == self.selected_option_id),
                None,
            )
            if selected is None:
                raise ValueError("selected option must appear in candidates")
            if not selected.eligible:
                raise ValueError("selected option must be eligible")
            if self.deferral_reason is not None:
                raise ValueError("a selected decision cannot have a deferral reason")

    def to_json(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id.to_json(),
            "requestId": self.request_id.to_json(),
            "workloadId": self.workload_id.to_json(),
            "policyVersion": self.policy_version.to_json(),
            "snapshotVersion": self.snapshot_version.to_json(),
            "candidates": [candidate.to_json() for candidate in self.candidates],
            "selectedOptionId": (
                None if self.selected_option_id is None else self.selected_option_id.to_json()
            ),
            "selectionProbability": self.selection_probability.to_json(),
            "randomizationSeed": self.randomization_seed,
            "deferralReason": self.deferral_reason,
        }

    @classmethod
    def from_json(cls, value: object) -> DecisionRecord:
        obj = require_mapping(value, "decision record")
        require_exact_keys(
            obj,
            "decision record",
            {
                "decisionId",
                "requestId",
                "workloadId",
                "policyVersion",
                "snapshotVersion",
                "candidates",
                "selectedOptionId",
                "selectionProbability",
                "randomizationSeed",
                "deferralReason",
            },
        )
        candidates = obj["candidates"]
        if not isinstance(candidates, list):
            raise TypeError("candidates must be an array")
        selected = obj["selectedOptionId"]
        deferral = obj["deferralReason"]
        if deferral is not None and not isinstance(deferral, str):
            raise TypeError("deferralReason must be a string or null")
        return cls(
            decision_id=DecisionId.from_json(obj["decisionId"]),
            request_id=RequestId.from_json(obj["requestId"]),
            workload_id=WorkloadId.from_json(obj["workloadId"]),
            policy_version=PolicyVersion.from_json(obj["policyVersion"]),
            snapshot_version=SnapshotVersion.from_json(obj["snapshotVersion"]),
            candidates=tuple(CandidateDecision.from_json(item) for item in candidates),
            selected_option_id=None if selected is None else OptionId.from_json(selected),
            selection_probability=Probability.from_json(obj["selectionProbability"]),
            randomization_seed=require_text(obj["randomizationSeed"], "randomizationSeed"),
            deferral_reason=deferral,
        )
