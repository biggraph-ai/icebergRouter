"""Increment 8 orchestration from a logged policy decision to guarded execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from types import MappingProxyType
from typing import Mapping

from iceberg_router.contracts.decisions import DecisionRecord, EstimateState
from iceberg_router.contracts.identifiers import BudgetId, EventId, OptionId
from iceberg_router.contracts.routing import PolicyRequest, RoutingPolicy

from .executor import (
    Clock,
    ExecutionRequest,
    ExecutionResult,
    IdentityFactory,
    OptionExecutor,
    RandomIdentityFactory,
    UtcClock,
)
from .graph import ValidatedOption
from .execution_store import ExecutionClaimState, SQLiteExecutionStore
from .journal import SQLiteAuditJournal, _canonical_payload


class RoutingConfigurationError(ValueError):
    """The policy snapshot cannot safely be mapped to executable options."""


class PolicyContractError(RuntimeError):
    """A policy returned a decision inconsistent with its immutable request."""


@dataclass(frozen=True, slots=True)
class RouteRequest:
    policy_request: PolicyRequest
    budget_id: BudgetId
    options: Mapping[OptionId, ValidatedOption]
    payload: object = None

    def __post_init__(self) -> None:
        if not isinstance(self.policy_request, PolicyRequest):
            raise TypeError("policy_request must be PolicyRequest")
        if not isinstance(self.budget_id, BudgetId):
            raise TypeError("budget_id must be BudgetId")
        if not isinstance(self.options, Mapping):
            raise TypeError("options must be a mapping")
        copied = dict(self.options)
        if any(not isinstance(key, OptionId) for key in copied):
            raise TypeError("option keys must be OptionId values")
        if any(not isinstance(value, ValidatedOption) for value in copied.values()):
            raise TypeError("option values must be ValidatedOption values")
        candidate_ids = {item.option_id for item in self.policy_request.candidates}
        if set(copied) != candidate_ids:
            raise RoutingConfigurationError(
                "executable options must exactly match the candidate snapshot"
            )
        for option_id, option in copied.items():
            if option.definition.option_id != option_id:
                raise RoutingConfigurationError("option key does not match its definition")
        for candidate in self.policy_request.candidates:
            if not candidate.eligible:
                continue
            if (
                candidate.upper_liability.state is not EstimateState.KNOWN
                or candidate.upper_liability.amount is None
            ):
                raise RoutingConfigurationError(
                    "eligible options require a known upper liability"
                )
            if candidate.upper_liability.amount < copied[candidate.option_id].max_path_liability:
                raise RoutingConfigurationError(
                    "candidate upper liability is below the validated graph bound"
                )
        object.__setattr__(self, "options", MappingProxyType(copied))


class RouteState(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RouteResult:
    decision: DecisionRecord | None
    execution: ExecutionResult | None
    state: RouteState = RouteState.COMPLETED


class IcebergRouter:
    """Coordinate pure selection, durable decision audit, and guarded execution."""

    def __init__(
        self,
        policy: RoutingPolicy,
        executor: OptionExecutor,
        journal: SQLiteAuditJournal,
        *,
        identity_factory: IdentityFactory | None = None,
        clock: Clock | None = None,
        execution_store: SQLiteExecutionStore | None = None,
    ):
        if not isinstance(policy, RoutingPolicy):
            raise TypeError("policy must implement RoutingPolicy")
        if not isinstance(executor, OptionExecutor):
            raise TypeError("executor must be OptionExecutor")
        if not isinstance(journal, SQLiteAuditJournal):
            raise TypeError("journal must be SQLiteAuditJournal")
        self.policy = policy
        self.executor = executor
        self.journal = journal
        self.identity_factory = identity_factory or RandomIdentityFactory()
        self.clock = clock or UtcClock()
        self.execution_store = execution_store or SQLiteExecutionStore(
            f"{journal.path}.executions.sqlite3"
        )

    def route(self, request: RouteRequest) -> RouteResult:
        if not isinstance(request, RouteRequest):
            raise TypeError("request must be RouteRequest")
        fingerprint = self._fingerprint(request)
        request_id = request.policy_request.request_id
        claim = self.execution_store.claim(request_id, fingerprint)
        if claim.state is ExecutionClaimState.COMPLETED:
            assert claim.result is not None
            return RouteResult(claim.result[0], claim.result[1], RouteState.COMPLETED)
        if claim.state is ExecutionClaimState.IN_PROGRESS:
            return RouteResult(None, None, RouteState.IN_PROGRESS)
        if claim.state is ExecutionClaimState.UNKNOWN:
            return RouteResult(None, None, RouteState.UNKNOWN)
        try:
            decision = self.policy.select(request.policy_request)
            self._validate_decision(request.policy_request, decision)
            decision_time = self.clock.now()
            self.journal.append_decision(
                EventId(self.identity_factory.new_id("event")),
                decision_time,
                decision,
                f"decision:{decision.decision_id.value}",
            )
            if decision.selected_option_id is None:
                result = RouteResult(decision, None)
                self.execution_store.append_transition(
                    request_id,
                    "terminal_completed",
                    {"status": "deferred", "decisionId": decision.decision_id.value},
                )
                self.execution_store.complete(
                    request_id, fingerprint, decision, None
                )
                return result

            execution_request = ExecutionRequest(
                request_id=decision.request_id,
                decision_id=decision.decision_id,
                budget_id=request.budget_id,
                option=request.options[decision.selected_option_id],
                applicable=True,
                payload=request.payload,
            )
            execution = self.executor.execute(
                execution_request, transition_sink=self.execution_store
            )
            self.journal.record_execution(
                EventId(self.identity_factory.new_id("event")),
                self.clock.now(),
                execution_request,
                execution,
                f"execution:{decision.decision_id.value}",
            )
            self.execution_store.append_transition(
                request_id,
                "terminal_completed",
                {
                    "status": execution.status.value,
                    "resultCode": execution.result_code,
                    "outputReference": execution.output_reference,
                },
            )
            self.execution_store.complete(
                request_id, fingerprint, decision, execution
            )
            return RouteResult(decision, execution)
        except BaseException:
            self.execution_store.mark_unknown(request_id)
            raise

    def _fingerprint(self, request: RouteRequest) -> str:
        policy = request.policy_request
        policy_version = getattr(self.policy, "policy_version", None)
        if policy_version is None or not hasattr(policy_version, "value"):
            raise RoutingConfigurationError(
                "durable routing requires an explicit policy_version"
            )
        material = {
            "schemaVersion": "1",
            "budgetId": request.budget_id.value,
            "policyVersion": policy_version.value,
            "policyRequest": {
                "decisionId": policy.decision_id.value,
                "requestId": policy.request_id.value,
                "workloadId": policy.workload_id.value,
                "snapshotVersion": policy.snapshot_version.value,
                "candidates": [candidate.to_json() for candidate in policy.candidates],
                "randomizationSeed": policy.randomization_seed,
                "taskFeatures": {
                    "taskFamily": policy.task_features.task_family,
                    "attributes": list(policy.task_features.attributes),
                    "version": policy.task_features.version,
                },
                "configurationSnapshot": {
                    "version": policy.configuration_snapshot.version,
                    "options": {
                        option_id.value: {
                            "optionVersion": frozen.option_version,
                            "resourceRevision": frozen.resource_revision,
                            "promptRevision": frozen.prompt_revision,
                            "checkerRevision": frozen.checker_revision,
                        }
                        for option_id, frozen in sorted(
                            policy.configuration_snapshot.options.items(),
                            key=lambda item: item[0].value,
                        )
                    },
                },
            },
            "options": {
                option_id.value: option.definition.to_json()
                for option_id, option in sorted(
                    request.options.items(), key=lambda item: item[0].value
                )
            },
            "payload": request.payload,
        }
        try:
            encoded = _canonical_payload(material).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise RoutingConfigurationError(
                "route payload must be canonical JSON for durable replay"
            ) from error
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _validate_decision(request: PolicyRequest, decision: object) -> None:
        if not isinstance(decision, DecisionRecord):
            raise PolicyContractError("policy must return DecisionRecord")
        if (
            decision.decision_id != request.decision_id
            or decision.request_id != request.request_id
            or decision.workload_id != request.workload_id
            or decision.snapshot_version != request.snapshot_version
            or decision.candidates != request.candidates
            or decision.randomization_seed != request.randomization_seed
        ):
            raise PolicyContractError("policy changed immutable request fields")
