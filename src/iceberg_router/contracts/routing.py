"""Provider-independent routing policy request and protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ._validation import require_text
from .decisions import CandidateDecision, DecisionRecord
from .identifiers import DecisionId, RequestId, SnapshotVersion, WorkloadId


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    """Immutable policy-visible candidate snapshot supplied by orchestration.

    Eligibility and both cost estimates are computed before this boundary. A
    policy selects from the snapshot; it does not authorize spend or reinterpret
    unknown estimates as zero.
    """

    decision_id: DecisionId
    request_id: RequestId
    workload_id: WorkloadId
    snapshot_version: SnapshotVersion
    candidates: tuple[CandidateDecision, ...]
    randomization_seed: str

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.decision_id, DecisionId, "decision_id"),
            (self.request_id, RequestId, "request_id"),
            (self.workload_id, WorkloadId, "workload_id"),
            (self.snapshot_version, SnapshotVersion, "snapshot_version"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field} must be {expected.__name__}")
        if not isinstance(self.candidates, tuple) or not self.candidates:
            raise ValueError("candidates must be a non-empty tuple")
        if any(not isinstance(item, CandidateDecision) for item in self.candidates):
            raise TypeError("candidates must contain CandidateDecision values")
        if len({item.option_id for item in self.candidates}) != len(self.candidates):
            raise ValueError("candidate option IDs must be unique")
        require_text(self.randomization_seed, "randomization_seed", maximum=256)


@runtime_checkable
class RoutingPolicy(Protocol):
    """A pure selector that cannot authorize or execute an option."""

    def select(self, request: PolicyRequest) -> DecisionRecord: ...
