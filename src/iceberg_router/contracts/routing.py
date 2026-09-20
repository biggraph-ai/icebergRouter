"""Provider-independent routing policy request and protocol."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from ._validation import require_text
from .decisions import CandidateDecision, DecisionRecord
from .identifiers import DecisionId, OptionId, RequestId, SnapshotVersion, WorkloadId


@dataclass(frozen=True, slots=True)
class TaskFeatures:
    task_family: str
    attributes: tuple[str, ...]
    version: str

    def __post_init__(self) -> None:
        require_text(self.task_family, "task_family", maximum=128)
        require_text(self.version, "version", maximum=128)
        if not isinstance(self.attributes, tuple):
            raise TypeError("attributes must be a tuple")
        for attribute in self.attributes:
            require_text(attribute, "attribute", maximum=128)
        if len(self.attributes) != len(set(self.attributes)):
            raise ValueError("task feature attributes must be unique")


@dataclass(frozen=True, slots=True)
class FrozenOptionVersion:
    option_version: str
    resource_revision: str
    prompt_revision: str
    checker_revision: str | None

    def __post_init__(self) -> None:
        for value, field in (
            (self.option_version, "option_version"),
            (self.resource_revision, "resource_revision"),
            (self.prompt_revision, "prompt_revision"),
        ):
            require_text(value, field, maximum=128)
        if self.checker_revision is not None:
            require_text(self.checker_revision, "checker_revision", maximum=128)


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    version: str
    options: Mapping[OptionId, FrozenOptionVersion]

    def __post_init__(self) -> None:
        require_text(self.version, "version", maximum=128)
        if not isinstance(self.options, Mapping) or not self.options:
            raise ValueError("options must be a non-empty mapping")
        copied = dict(self.options)
        if any(not isinstance(key, OptionId) for key in copied):
            raise TypeError("configuration option keys must be OptionId")
        if any(not isinstance(value, FrozenOptionVersion) for value in copied.values()):
            raise TypeError("configuration values must be FrozenOptionVersion")
        object.__setattr__(self, "options", MappingProxyType(copied))


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
    task_features: TaskFeatures
    configuration_snapshot: ConfigurationSnapshot

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.decision_id, DecisionId, "decision_id"),
            (self.request_id, RequestId, "request_id"),
            (self.workload_id, WorkloadId, "workload_id"),
            (self.snapshot_version, SnapshotVersion, "snapshot_version"),
            (self.task_features, TaskFeatures, "task_features"),
            (
                self.configuration_snapshot,
                ConfigurationSnapshot,
                "configuration_snapshot",
            ),
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
        if set(self.configuration_snapshot.options) != {
            candidate.option_id for candidate in self.candidates
        }:
            raise ValueError("configuration snapshot must cover every candidate exactly")


@runtime_checkable
class RoutingPolicy(Protocol):
    """A pure selector that cannot authorize or execute an option."""

    def select(self, request: PolicyRequest) -> DecisionRecord: ...
