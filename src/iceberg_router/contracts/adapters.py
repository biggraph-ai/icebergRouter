"""Provider-independent operation adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .events import UsageState
from .identifiers import (
    AttemptId,
    AuthorizationId,
    DecisionId,
    RequestId,
    ReservationId,
)
from .money import Nanodollars
from .options import BranchOutcome, OperationNode


@dataclass(frozen=True, slots=True)
class OperationContext:
    """One already-authorized physical operation attempt."""

    request_id: RequestId
    decision_id: DecisionId
    node: OperationNode
    attempt_number: int
    attempt_id: AttemptId
    authorization_id: AuthorizationId
    reservation_id: ReservationId
    payload: object

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.request_id, RequestId, "request_id"),
            (self.decision_id, DecisionId, "decision_id"),
            (self.node, OperationNode, "node"),
            (self.attempt_id, AttemptId, "attempt_id"),
            (self.authorization_id, AuthorizationId, "authorization_id"),
            (self.reservation_id, ReservationId, "reservation_id"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field} must be {expected.__name__}")
        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be positive")


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Normalized outcome and authoritative-or-unknown usage for one attempt."""

    outcome: BranchOutcome
    usage_state: UsageState
    actual_cost: Nanodollars | None
    output_reference: str | None = None
    provider_receipt: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, BranchOutcome):
            raise TypeError("outcome must be BranchOutcome")
        if self.outcome is BranchOutcome.UNFUNDED:
            raise ValueError("adapters cannot report the governor-owned unfunded outcome")
        if not isinstance(self.usage_state, UsageState):
            raise TypeError("usage_state must be UsageState")
        if self.usage_state is UsageState.KNOWN and not isinstance(
            self.actual_cost, Nanodollars
        ):
            raise ValueError("known usage requires actual_cost")
        if self.usage_state is UsageState.UNKNOWN and self.actual_cost is not None:
            raise ValueError("unknown usage cannot carry actual_cost")
        for value, field in (
            (self.output_reference, "output_reference"),
            (self.provider_receipt, "provider_receipt"),
        ):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{field} must be a non-empty string or None")


@runtime_checkable
class OperationAdapter(Protocol):
    """Structural interface consumed by the guarded executor."""

    def execute(self, context: OperationContext) -> OperationResult: ...
