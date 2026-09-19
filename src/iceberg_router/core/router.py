"""Increment 8 orchestration from a logged policy decision to guarded execution."""

from __future__ import annotations

from dataclasses import dataclass
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
from .journal import SQLiteAuditJournal


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


@dataclass(frozen=True, slots=True)
class RouteResult:
    decision: DecisionRecord
    execution: ExecutionResult | None


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

    def route(self, request: RouteRequest) -> RouteResult:
        if not isinstance(request, RouteRequest):
            raise TypeError("request must be RouteRequest")
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
            return RouteResult(decision, None)

        execution_request = ExecutionRequest(
            request_id=decision.request_id,
            decision_id=decision.decision_id,
            budget_id=request.budget_id,
            option=request.options[decision.selected_option_id],
            applicable=True,
            payload=request.payload,
        )
        execution = self.executor.execute(execution_request)
        self.journal.record_execution(
            EventId(self.identity_factory.new_id("event")),
            self.clock.now(),
            execution_request,
            execution,
            f"execution:{decision.decision_id.value}",
        )
        return RouteResult(decision, execution)

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
