"""Provider-independent operation adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from ._validation import require_exact_keys, require_mapping, require_text
from .events import UsageState
from .identifiers import (
    AttemptId,
    AuthorizationId,
    DecisionId,
    RequestId,
    ReservationId,
)
from .money import Nanodollars
from .options import ArtifactRole, BranchOutcome, OperationNode


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Protected reference to a versioned artifact; it never contains artifact data."""

    reference: str
    role: ArtifactRole
    version: str
    producer_node_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.reference, str) or not self.reference:
            raise ValueError("reference must be a non-empty string")
        if not isinstance(self.role, ArtifactRole):
            raise TypeError("role must be ArtifactRole")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if self.producer_node_id is not None and (
            not isinstance(self.producer_node_id, str) or not self.producer_node_id
        ):
            raise ValueError("producer_node_id must be a non-empty string or None")

    def to_json(self) -> dict[str, str | None]:
        return {
            "schemaVersion": "1",
            "reference": self.reference,
            "role": self.role.value,
            "artifactVersion": self.version,
            "producerNodeId": self.producer_node_id,
        }

    @classmethod
    def from_json(cls, value: object) -> ArtifactReference:
        obj = require_mapping(value, "artifact reference")
        require_exact_keys(
            obj,
            "artifact reference",
            {
                "schemaVersion",
                "reference",
                "role",
                "artifactVersion",
                "producerNodeId",
            },
        )
        if obj["schemaVersion"] != "1":
            raise ValueError("unsupported artifact reference schemaVersion")
        try:
            role = ArtifactRole(obj["role"])
        except (TypeError, ValueError) as error:
            raise ValueError("artifact reference role is invalid") from error
        producer = obj["producerNodeId"]
        return cls(
            require_text(obj["reference"], "reference", maximum=1024),
            role,
            require_text(obj["artifactVersion"], "artifactVersion", maximum=128),
            None
            if producer is None
            else require_text(producer, "producerNodeId", maximum=128),
        )


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
    inputs: Mapping[str, ArtifactReference]

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
        if not isinstance(self.inputs, Mapping):
            raise TypeError("inputs must be a mapping")
        copied = dict(self.inputs)
        if any(not isinstance(name, str) or not name for name in copied):
            raise ValueError("input names must be non-empty strings")
        if any(not isinstance(value, ArtifactReference) for value in copied.values()):
            raise TypeError("inputs must contain ArtifactReference values")
        object.__setattr__(self, "inputs", MappingProxyType(copied))


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

@dataclass(frozen=True, slots=True)
class ReconciliationRequest:
    """Provider lookup for an already dispatched attempt; never authorizes a retry."""

    attempt_id: AttemptId
    authorization_id: AuthorizationId
    reservation_id: ReservationId
    provider_receipt: str | None = None

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.attempt_id, AttemptId, "attempt_id"),
            (self.authorization_id, AuthorizationId, "authorization_id"),
            (self.reservation_id, ReservationId, "reservation_id"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field} must be {expected.__name__}")
        if self.provider_receipt is not None and not self.provider_receipt:
            raise ValueError("provider_receipt must be non-empty or None")


@runtime_checkable
class OperationReconciler(Protocol):
    """Optional provider lookup; returning None keeps liability unresolved."""

    def reconcile(self, request: ReconciliationRequest) -> OperationResult | None: ...
