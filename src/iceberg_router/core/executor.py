"""Guarded execution of validated bounded option graphs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Protocol
from uuid import uuid4

from iceberg_router.contracts.adapters import (
    OperationAdapter,
    OperationContext,
    OperationResult,
)
from iceberg_router.contracts.decisions import CostEstimate, EstimateState
from iceberg_router.contracts.events import TraceEvent, TraceEventKind, UsageState
from iceberg_router.contracts.identifiers import (
    AttemptId,
    AuthorizationId,
    BudgetId,
    DecisionId,
    EventId,
    NodeId,
    RequestId,
    ReservationId,
)
from iceberg_router.contracts.options import (
    BranchOutcome,
    OperationKind,
    OperationNode,
    TerminalNode,
    TerminalStatus,
)

from .governor import AdmissionRequest, BoundUnavailable, BudgetGovernor
from .graph import ValidatedOption
from .ledger import AdmissionDenied, BudgetContractBreach


class ExecutorConfigurationError(ValueError):
    """The executor cannot safely run the supplied option."""


class IdentityFactory(Protocol):
    def new_id(self, category: str) -> str: ...


class Clock(Protocol):
    def now(self) -> str: ...


class RandomIdentityFactory:
    def new_id(self, category: str) -> str:
        return f"{category}-{uuid4().hex}"


class UtcClock:
    def now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    request_id: RequestId
    decision_id: DecisionId
    budget_id: BudgetId
    option: ValidatedOption
    applicable: bool
    payload: object = None

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.request_id, RequestId, "request_id"),
            (self.decision_id, DecisionId, "decision_id"),
            (self.budget_id, BudgetId, "budget_id"),
            (self.option, ValidatedOption, "option"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field} must be {expected.__name__}")
        if not isinstance(self.applicable, bool):
            raise TypeError("applicable must be bool")


@dataclass(frozen=True, slots=True)
class AttemptExecution:
    node_id: NodeId
    attempt_number: int
    attempt_id: AttemptId
    authorization_id: AuthorizationId
    reservation_id: ReservationId
    result: OperationResult


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    status: TerminalStatus
    result_code: str
    terminal_node_id: NodeId | None
    output_reference: str | None
    attempts: tuple[AttemptExecution, ...]
    trace: tuple[TraceEvent, ...]


class OptionExecutor:
    """Execute one validated graph while authorizing every physical attempt."""

    def __init__(
        self,
        governor: BudgetGovernor,
        adapters: Mapping[OperationKind, OperationAdapter],
        *,
        identity_factory: IdentityFactory | None = None,
        clock: Clock | None = None,
    ):
        if not isinstance(governor, BudgetGovernor):
            raise TypeError("governor must be BudgetGovernor")
        if not isinstance(adapters, Mapping):
            raise TypeError("adapters must be a mapping")
        if any(not isinstance(kind, OperationKind) for kind in adapters):
            raise TypeError("adapter keys must be OperationKind values")
        self.governor = governor
        self.adapters = MappingProxyType(dict(adapters))
        self.identity_factory = identity_factory or RandomIdentityFactory()
        self.clock = clock or UtcClock()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not isinstance(request, ExecutionRequest):
            raise TypeError("request must be ExecutionRequest")
        definition = request.option.definition
        nodes = {node.node_id: node for node in definition.nodes}
        required_adapters = {
            node.kind for node in definition.nodes if isinstance(node, OperationNode)
        }
        missing = sorted(kind.value for kind in required_adapters - self.adapters.keys())
        if missing:
            raise ExecutorConfigurationError(f"missing adapters for operation kinds: {missing}")

        trace: list[TraceEvent] = []
        attempts: list[AttemptExecution] = []
        sequence = 0

        def emit(
            kind: TraceEventKind,
            node_id: NodeId,
            detail_code: str,
            *,
            attempt_id: AttemptId | None = None,
            authorization_id: AuthorizationId | None = None,
        ) -> None:
            nonlocal sequence
            trace.append(
                TraceEvent(
                    event_id=EventId(self.identity_factory.new_id("event")),
                    request_id=request.request_id,
                    decision_id=request.decision_id,
                    option_id=definition.option_id,
                    sequence=sequence,
                    kind=kind,
                    occurred_at=self.clock.now(),
                    detail_code=detail_code,
                    attempt_id=attempt_id,
                    authorization_id=authorization_id,
                )
            )
            sequence += 1

        emit(TraceEventKind.OPTION_STARTED, definition.entry_node_id, "option_started")
        if not request.applicable:
            emit(
                TraceEventKind.OPTION_DEFERRED,
                definition.entry_node_id,
                "applicability_rejected",
            )
            return ExecutionResult(
                TerminalStatus.DEFERRED,
                "inapplicable",
                None,
                None,
                tuple(attempts),
                tuple(trace),
            )

        current_id = definition.entry_node_id
        transitions = 0
        while True:
            node = nodes[current_id]
            if isinstance(node, TerminalNode):
                terminal_event = {
                    TerminalStatus.COMPLETE: TraceEventKind.OPTION_FINISHED,
                    TerminalStatus.DEFERRED: TraceEventKind.OPTION_DEFERRED,
                    TerminalStatus.FAILED: TraceEventKind.OPTION_FAILED,
                }[node.status]
                emit(terminal_event, node.node_id, node.result_code)
                return ExecutionResult(
                    node.status,
                    node.result_code,
                    node.node_id,
                    self._latest_output(attempts),
                    tuple(attempts),
                    tuple(trace),
                )
            emit(TraceEventKind.NODE_STARTED, node.node_id, node.kind.value)
            outcome, breach = self._execute_node(request, node, attempts, emit)
            if breach:
                return ExecutionResult(
                    TerminalStatus.FAILED,
                    "budget_contract_breach",
                    None,
                    self._latest_output(attempts),
                    tuple(attempts),
                    tuple(trace),
                )
            target = next(branch.target for branch in node.branches if branch.outcome is outcome)
            emit(TraceEventKind.BRANCH_SELECTED, node.node_id, outcome.value)
            transitions += 1
            if transitions > definition.max_transitions:
                raise RuntimeError("validated option exceeded its transition bound")
            current_id = target

    def _execute_node(
        self,
        request: ExecutionRequest,
        node: OperationNode,
        attempts: list[AttemptExecution],
        emit,
    ) -> tuple[BranchOutcome, bool]:
        definition = request.option.definition
        adapter = self.adapters[node.kind]
        last_outcome = BranchOutcome.ERROR
        for attempt_number in range(1, node.limits.max_attempts + 1):
            attempt_id = AttemptId(self.identity_factory.new_id("attempt"))
            authorization_id = AuthorizationId(self.identity_factory.new_id("authorization"))
            reservation_id = ReservationId(self.identity_factory.new_id("reservation"))
            admission = AdmissionRequest(
                budget_id=request.budget_id,
                reservation_id=reservation_id,
                request_id=request.request_id,
                decision_id=request.decision_id,
                account_id=node.account_id,
                upper_liability=CostEstimate(
                    EstimateState.KNOWN,
                    definition.bound_calculator_version.value,
                    node.liability_bound,
                ),
            )
            try:
                self.governor.authorize(
                    admission,
                    authorization_id=authorization_id,
                    attempt_id=attempt_id,
                )
            except (AdmissionDenied, BoundUnavailable):
                emit(TraceEventKind.ADMISSION_DENIED, node.node_id, "unfunded")
                return BranchOutcome.UNFUNDED, False

            emit(
                TraceEventKind.ATTEMPT_STARTED,
                node.node_id,
                f"attempt_{attempt_number}",
                attempt_id=attempt_id,
                authorization_id=authorization_id,
            )
            context = OperationContext(
                request_id=request.request_id,
                decision_id=request.decision_id,
                node=node,
                attempt_number=attempt_number,
                attempt_id=attempt_id,
                authorization_id=authorization_id,
                reservation_id=reservation_id,
                payload=request.payload,
            )
            try:
                result = adapter.execute(context)
                if not isinstance(result, OperationResult):
                    raise TypeError("adapter must return OperationResult")
            except Exception:
                result = OperationResult(
                    BranchOutcome.UNKNOWN,
                    UsageState.UNKNOWN,
                    None,
                )
            allowed = {branch.outcome for branch in node.branches}
            if result.outcome not in allowed:
                invalid_outcome = result.outcome
                result = OperationResult(
                    BranchOutcome.UNKNOWN,
                    result.usage_state,
                    result.actual_cost,
                    result.output_reference,
                    result.provider_receipt,
                )
                emit(
                    TraceEventKind.INVALID_OUTCOME,
                    node.node_id,
                    f"{invalid_outcome.value}_not_allowed",
                    attempt_id=attempt_id,
                    authorization_id=authorization_id,
                )

            attempt = AttemptExecution(
                node.node_id,
                attempt_number,
                attempt_id,
                authorization_id,
                reservation_id,
                result,
            )
            attempts.append(attempt)
            try:
                if result.usage_state is UsageState.KNOWN:
                    assert result.actual_cost is not None
                    self.governor.ledger.settle(
                        reservation_id,
                        actual_cost=result.actual_cost,
                        idempotency_key=f"settle:{attempt_id.value}",
                    )
                else:
                    self.governor.ledger.mark_pending(
                        reservation_id,
                        idempotency_key=f"pending:{attempt_id.value}",
                    )
            except BudgetContractBreach:
                emit(
                    TraceEventKind.BUDGET_BREACH,
                    node.node_id,
                    "actual_exceeded_bound",
                    attempt_id=attempt_id,
                    authorization_id=authorization_id,
                )
                return result.outcome, True
            emit(
                TraceEventKind.ATTEMPT_FINISHED,
                node.node_id,
                result.outcome.value,
                attempt_id=attempt_id,
                authorization_id=authorization_id,
            )
            last_outcome = result.outcome
            if result.outcome is not BranchOutcome.ERROR:
                return result.outcome, False
        return last_outcome, False

    @staticmethod
    def _latest_output(attempts: list[AttemptExecution]) -> str | None:
        return next(
            (
                attempt.result.output_reference
                for attempt in reversed(attempts)
                if attempt.result.output_reference is not None
            ),
            None,
        )
