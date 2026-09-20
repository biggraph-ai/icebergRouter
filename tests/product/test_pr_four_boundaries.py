"""PR 4 reviewed resource, pricing, deadline, and transport fixtures."""

from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest
from collections import deque

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.adapters import (  # noqa: E402
    SandboxedToolAdapter, SingleAttemptAdapter, TransportDeadlineExceeded,
)
from iceberg_router.contracts import (  # noqa: E402
    ArtifactRole, BoundedContractEvidence, BranchOutcome, BudgetId, DecisionId,
    Nanodollars, OperationContext, OperationKind, OperationLimits, OperationResult,
    RequestId, ResourceIdentity, UsageState,
)
from iceberg_router.core import (  # noqa: E402
    BudgetGovernor, ExecutionRequest, GraphValidationError, OptionExecutor,
    SQLiteBudgetLedger, Tariff, calculate_attempt_bound, validate_option,
)
from tests.product.test_increment_eight_router import (  # noqa: E402
    MODEL_RESOURCE, validated_option,
)
from tests.product.test_increment_four_executor import (  # noqa: E402
    MODEL_RESOURCE as EXECUTOR_RESOURCE,
    single_model_option,
)
from tests.product.test_increment_seven_adapters import context  # noqa: E402


class ReviewedBoundaryTests(unittest.TestCase):
    def test_exact_tariff_bound_includes_caps_non_token_charge_and_rounding(self):
        tariff = Tariff(
            "tariff-v1", MODEL_RESOURCE, Nanodollars(2), Nanodollars(3),
            Nanodollars(10), Nanodollars(7), Nanodollars(10),
        )
        bound = calculate_attempt_bound(
            tariff, OperationLimits(2, 1000, 100, 50),
            calculator_version="calculator-v1",
        )
        self.assertEqual(bound, Nanodollars(370))

    def test_unreviewed_bound_contract_is_not_strictly_eligible(self):
        option = validated_option().definition
        operation = option.nodes[0]
        unreviewed = replace(
            operation,
            bounded_contract=BoundedContractEvidence(
                "evidence-v1", "tariff-v1", "bound-v1", Nanodollars(10),
                False, True, True
            ),
        )
        with self.assertRaisesRegex(GraphValidationError, "reviewed bounded-contract"):
            validate_option(replace(option, nodes=(unreviewed, *option.nodes[1:])))

    def test_resource_substitution_is_rejected_before_transport(self):
        calls = []
        other = ResourceIdentity("fixture", "other-model", "v1", "prompt-v1")
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", other,
            lambda operation_context: calls.append(operation_context),
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            adapter.execute(context())
        self.assertEqual(calls, [])

    def test_reviewed_transport_normal_error_cancellation_and_malformed(self):
        successful = OperationResult(
            BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(1), "answer"
        )
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", MODEL_RESOURCE,
            lambda _: successful,
        )
        model_context = replace(context(), node=replace(context().node, resource=MODEL_RESOURCE))
        self.assertEqual(adapter.execute(model_context), successful)

        for failure in (CancelledError(), RuntimeError("provider error")):
            with self.subTest(failure=type(failure).__name__):
                failing = SingleAttemptAdapter(
                    OperationKind.MODEL_CALL, "operation-v1", MODEL_RESOURCE,
                    lambda _, failure=failure: (_ for _ in ()).throw(failure),
                )
                with self.assertRaises(type(failure)):
                    failing.execute(model_context)

        malformed = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", MODEL_RESOURCE, lambda _: {},
        )
        with self.assertRaises(TypeError):
            malformed.execute(model_context)

    def test_one_millisecond_deadline_does_not_report_seventy_ms_work_as_timely(self):
        calls = []

        def slow(operation_context):
            calls.append(operation_context)
            time.sleep(0.07)
            return OperationResult(
                BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(1), "late"
            )

        base = context()
        timed_node = replace(
            base.node,
            limits=replace(base.node.limits, timeout_ms=1),
            resource=MODEL_RESOURCE,
        )
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", MODEL_RESOURCE, slow
        )
        started = time.monotonic()
        with self.assertRaises(TransportDeadlineExceeded):
            adapter.execute(replace(base, node=timed_node))
        self.assertLess(time.monotonic() - started, 0.05)
        self.assertEqual(len(calls), 1)

    def test_timeout_remains_pending_without_authoritative_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget = BudgetId("budget-1")
            ledger.create_budget(budget, Nanodollars(100))
            validated = single_model_option()
            operation = validated.definition.nodes[0]
            timed_operation = replace(
                operation, limits=replace(operation.limits, timeout_ms=1)
            )
            timed = validate_option(
                replace(
                    validated.definition,
                    nodes=(timed_operation, *validated.definition.nodes[1:]),
                )
            )
            adapter = SingleAttemptAdapter(
                OperationKind.MODEL_CALL, "model-v1", EXECUTOR_RESOURCE,
                lambda _: (time.sleep(0.07), None)[1],
            )
            result = OptionExecutor(
                BudgetGovernor(ledger), {EXECUTOR_RESOURCE: adapter}
            ).execute(ExecutionRequest(
                RequestId("request-1"), DecisionId("decision-1"), budget, timed, True,
                {"prompt": "offline"},
            ))
            self.assertEqual(result.attempts[0].result.usage_state, UsageState.UNKNOWN)
            self.assertEqual(ledger.snapshot(budget).outstanding_liability, Nanodollars(10))

    def test_delayed_billing_reconciles_the_retained_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget = BudgetId("budget-1")
            ledger.create_budget(budget, Nanodollars(100))
            validated = single_model_option()
            operation = validated.definition.nodes[0]
            timed = validate_option(replace(
                validated.definition,
                nodes=(replace(operation, limits=replace(operation.limits, timeout_ms=1)),
                       *validated.definition.nodes[1:]),
            ))
            adapter = SingleAttemptAdapter(
                OperationKind.MODEL_CALL, "model-v1", EXECUTOR_RESOURCE,
                lambda _: (time.sleep(0.07), OperationResult(
                    BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(4), "late"
                ))[1],
            )
            result = OptionExecutor(
                BudgetGovernor(ledger), {EXECUTOR_RESOURCE: adapter}
            ).execute(ExecutionRequest(
                RequestId("request-1"), DecisionId("decision-1"), budget, timed, True,
            ))
            reservation = result.attempts[0].reservation_id
            ledger.settle(
                reservation, actual_cost=Nanodollars(4), idempotency_key="delayed:invoice"
            )
            snapshot = ledger.snapshot(budget)
            self.assertEqual(snapshot.confirmed_spend, Nanodollars(4))
            self.assertEqual(snapshot.outstanding_liability, Nanodollars(0))
            time.sleep(0.08)  # let the deliberately uncancellable transport finish

    def test_executor_retries_are_separately_authorized_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget = BudgetId("budget-1")
            ledger.create_budget(budget, Nanodollars(100))
            steps = deque((
                OperationResult(BranchOutcome.ERROR, UsageState.KNOWN, Nanodollars(1)),
                OperationResult(
                    BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(2), "answer"
                ),
            ))
            adapter = SingleAttemptAdapter(
                OperationKind.MODEL_CALL, "model-v1", EXECUTOR_RESOURCE,
                lambda _: steps.popleft(),
            )
            result = OptionExecutor(
                BudgetGovernor(ledger), {EXECUTOR_RESOURCE: adapter}
            ).execute(ExecutionRequest(
                RequestId("request-1"), DecisionId("decision-1"), budget,
                single_model_option(attempts=2), True,
            ))
            self.assertEqual(len(result.attempts), 2)
            self.assertEqual(
                [event["eventKind"] for event in ledger.outbox_events()],
                ["authorization", "settlement", "authorization", "settlement"],
            )

    def test_reviewed_transport_over_bound_invoice_is_recorded_and_halts(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget = BudgetId("budget-1")
            ledger.create_budget(budget, Nanodollars(100))
            adapter = SingleAttemptAdapter(
                OperationKind.MODEL_CALL, "model-v1", EXECUTOR_RESOURCE,
                lambda _: OperationResult(
                    BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(20), "answer"
                ),
            )
            result = OptionExecutor(
                BudgetGovernor(ledger), {EXECUTOR_RESOURCE: adapter}
            ).execute(ExecutionRequest(
                RequestId("request-1"), DecisionId("decision-1"), budget,
                single_model_option(liability=5), True,
            ))
            self.assertEqual(result.result_code, "budget_contract_breach")
            self.assertEqual(ledger.snapshot(budget).confirmed_spend, Nanodollars(20))
            self.assertTrue(ledger.snapshot(budget).halted)

    def test_local_tool_process_is_terminated_at_deadline(self):
        tool_context = context(OperationKind.DETERMINISTIC_TOOL)
        tool_resource = tool_context.node.resource
        timed = replace(
            tool_context,
            node=replace(tool_context.node, limits=replace(tool_context.node.limits, timeout_ms=1)),
        )
        adapter = SandboxedToolAdapter(
            "operation-v1", tool_resource,
            lambda _: (time.sleep(0.07), OperationResult(
                BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(0), "tool"
            ))[1],
        )
        with self.assertRaises(TransportDeadlineExceeded):
            adapter.execute(timed)


if __name__ == "__main__":
    unittest.main()
