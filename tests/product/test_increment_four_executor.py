from pathlib import Path
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AccountId,
    ApplicabilityRule,
    ApplicabilityVersion,
    BoundVersion,
    Branch,
    BranchOutcome,
    BudgetId,
    DecisionId,
    EstimatorVersion,
    Nanodollars,
    NodeId,
    OperationKind,
    OperationLimits,
    OperationNode,
    OptionDefinition,
    OptionId,
    OptionVersion,
    RequestId,
    TerminalNode,
    TerminalStatus,
    TraceEventKind,
    UsageState,
)
from iceberg_router.core import (  # noqa: E402
    BudgetGovernor,
    ExecutionRequest,
    ExecutorConfigurationError,
    OperationResult,
    OptionExecutor,
    SQLiteBudgetLedger,
    validate_option,
)
from iceberg_router.testing import (  # noqa: E402
    DeterministicIdentityFactory,
    FixedClock,
    ScriptedAdapter,
)


def limits(attempts: int = 1) -> OperationLimits:
    return OperationLimits(attempts, 1_000, 100, 50)


def branch(outcome: BranchOutcome, target: str) -> Branch:
    return Branch(outcome, NodeId(target))


def model_node(
    name: str,
    *,
    success: str,
    error: str,
    unknown: str,
    unfunded: str,
    attempts: int = 1,
    liability: int = 10,
) -> OperationNode:
    return OperationNode(
        NodeId(name),
        OperationKind.MODEL_CALL,
        AccountId("model-serving"),
        Nanodollars(liability),
        limits(attempts),
        "model-v1",
        (
            branch(BranchOutcome.SUCCESS, success),
            branch(BranchOutcome.ERROR, error),
            branch(BranchOutcome.UNKNOWN, unknown),
            branch(BranchOutcome.UNFUNDED, unfunded),
        ),
    )


def definition(nodes: tuple, *, transitions: int, attempts: int) -> OptionDefinition:
    return OptionDefinition(
        OptionId("test-option"),
        OptionVersion("option-v1"),
        NodeId("start"),
        ApplicabilityRule("test-rule", ApplicabilityVersion("applicability-v1")),
        EstimatorVersion("expected-v1"),
        BoundVersion("bound-v1"),
        transitions,
        attempts,
        nodes,
    )


def single_model_option(*, attempts: int = 1, liability: int = 10):
    return validate_option(
        definition(
            (
                model_node(
                    "start",
                    success="complete",
                    error="failed",
                    unknown="defer",
                    unfunded="defer",
                    attempts=attempts,
                    liability=liability,
                ),
                TerminalNode(NodeId("complete"), TerminalStatus.COMPLETE, "answer_ready"),
                TerminalNode(NodeId("defer"), TerminalStatus.DEFERRED, "usage_unknown"),
                TerminalNode(NodeId("failed"), TerminalStatus.FAILED, "provider_error"),
            ),
            transitions=1,
            attempts=attempts,
        )
    )


def repair_option():
    verify = OperationNode(
        NodeId("verify"),
        OperationKind.VERIFY,
        AccountId("verification"),
        Nanodollars(3),
        limits(),
        "checker-v1",
        (
            branch(BranchOutcome.PASS, "complete"),
            branch(BranchOutcome.FAIL, "repair"),
            branch(BranchOutcome.UNKNOWN, "defer"),
            branch(BranchOutcome.ERROR, "defer"),
            branch(BranchOutcome.UNFUNDED, "defer"),
        ),
    )
    return validate_option(
        definition(
            (
                model_node(
                    "start",
                    success="verify",
                    error="failed",
                    unknown="defer",
                    unfunded="defer",
                    liability=10,
                ),
                verify,
                model_node(
                    "repair",
                    success="complete",
                    error="failed",
                    unknown="defer",
                    unfunded="defer",
                    liability=20,
                ),
                TerminalNode(NodeId("complete"), TerminalStatus.COMPLETE, "verified"),
                TerminalNode(NodeId("defer"), TerminalStatus.DEFERRED, "unfunded_or_unknown"),
                TerminalNode(NodeId("failed"), TerminalStatus.FAILED, "operation_failed"),
            ),
            transitions=3,
            attempts=3,
        )
    )


def known(outcome: BranchOutcome, cost: int, output: str | None = None) -> OperationResult:
    return OperationResult(outcome, UsageState.KNOWN, Nanodollars(cost), output)


class ExecutorTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "ledger.sqlite3"
        self.ledger = SQLiteBudgetLedger(self.path)
        self.budget_id = BudgetId("budget-1")

    def tearDown(self):
        self.temporary.cleanup()

    def make_executor(self, adapters, budget: int = 100) -> OptionExecutor:
        self.ledger.create_budget(self.budget_id, Nanodollars(budget))
        return OptionExecutor(
            BudgetGovernor(self.ledger),
            adapters,
            identity_factory=DeterministicIdentityFactory(),
            clock=FixedClock(),
        )

    def request(self, option, *, applicable: bool = True) -> ExecutionRequest:
        return ExecutionRequest(
            RequestId("request-1"),
            DecisionId("decision-1"),
            self.budget_id,
            option,
            applicable,
            {"prompt": "synthetic"},
        )


class ExecutionTests(ExecutorTestCase):
    def test_success_authorizes_settles_and_records_trace(self):
        adapter = ScriptedAdapter([known(BranchOutcome.SUCCESS, 4, "output-1")])
        executor = self.make_executor({OperationKind.MODEL_CALL: adapter})
        result = executor.execute(self.request(single_model_option()))

        self.assertEqual(TerminalStatus.COMPLETE, result.status)
        self.assertEqual("answer_ready", result.result_code)
        self.assertEqual("output-1", result.output_reference)
        self.assertEqual(1, len(result.attempts))
        self.assertEqual("output-1", result.attempts[0].result.output_reference)
        self.assertEqual(list(range(len(result.trace))), [event.sequence for event in result.trace])
        self.assertEqual(
            [
                TraceEventKind.OPTION_STARTED,
                TraceEventKind.NODE_STARTED,
                TraceEventKind.ATTEMPT_STARTED,
                TraceEventKind.ATTEMPT_FINISHED,
                TraceEventKind.BRANCH_SELECTED,
                TraceEventKind.OPTION_FINISHED,
            ],
            [event.kind for event in result.trace],
        )
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(4), snapshot.confirmed_spend)
        self.assertEqual(Nanodollars(0), snapshot.outstanding_liability)

    def test_known_error_retries_with_new_authorization(self):
        adapter = ScriptedAdapter(
            [known(BranchOutcome.ERROR, 2), known(BranchOutcome.SUCCESS, 3, "output-2")]
        )
        executor = self.make_executor({OperationKind.MODEL_CALL: adapter})
        result = executor.execute(self.request(single_model_option(attempts=2)))

        self.assertEqual(TerminalStatus.COMPLETE, result.status)
        self.assertEqual(2, len(result.attempts))
        self.assertEqual(2, len({attempt.attempt_id for attempt in result.attempts}))
        self.assertEqual(2, len({attempt.authorization_id for attempt in result.attempts}))
        self.assertEqual(2, len({attempt.reservation_id for attempt in result.attempts}))
        self.assertEqual(Nanodollars(5), self.ledger.snapshot(self.budget_id).confirmed_spend)

    def test_exception_becomes_unknown_usage_and_retains_hold(self):
        adapter = ScriptedAdapter([TimeoutError("synthetic timeout")])
        executor = self.make_executor({OperationKind.MODEL_CALL: adapter})
        result = executor.execute(self.request(single_model_option(liability=10)))

        self.assertEqual(TerminalStatus.DEFERRED, result.status)
        self.assertEqual(BranchOutcome.UNKNOWN, result.attempts[0].result.outcome)
        self.assertEqual(UsageState.UNKNOWN, result.attempts[0].result.usage_state)
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(0), snapshot.confirmed_spend)
        self.assertEqual(Nanodollars(10), snapshot.outstanding_liability)

    def test_unfunded_repair_follows_explicit_defer_branch(self):
        model = ScriptedAdapter([known(BranchOutcome.SUCCESS, 10)])
        verifier = ScriptedAdapter([known(BranchOutcome.FAIL, 3)])
        executor = self.make_executor(
            {OperationKind.MODEL_CALL: model, OperationKind.VERIFY: verifier}, budget=15
        )
        result = executor.execute(self.request(repair_option()))

        self.assertEqual(TerminalStatus.DEFERRED, result.status)
        self.assertEqual("unfunded_or_unknown", result.result_code)
        self.assertEqual(2, len(result.attempts))
        self.assertEqual(1, len(model.calls))
        self.assertIn(TraceEventKind.ADMISSION_DENIED, [event.kind for event in result.trace])
        self.assertEqual(Nanodollars(13), self.ledger.snapshot(self.budget_id).confirmed_spend)

    def test_bound_breach_fails_without_following_quality_branch(self):
        adapter = ScriptedAdapter([known(BranchOutcome.SUCCESS, 11)])
        executor = self.make_executor({OperationKind.MODEL_CALL: adapter})
        result = executor.execute(self.request(single_model_option(liability=10)))

        self.assertEqual(TerminalStatus.FAILED, result.status)
        self.assertEqual("budget_contract_breach", result.result_code)
        self.assertIsNone(result.terminal_node_id)
        self.assertIn(TraceEventKind.BUDGET_BREACH, [event.kind for event in result.trace])
        self.assertNotIn(TraceEventKind.BRANCH_SELECTED, [event.kind for event in result.trace])
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertTrue(snapshot.halted)
        self.assertEqual(Nanodollars(11), snapshot.confirmed_spend)

    def test_inapplicable_request_defers_without_authorization(self):
        adapter = ScriptedAdapter([known(BranchOutcome.SUCCESS, 1)])
        executor = self.make_executor({OperationKind.MODEL_CALL: adapter})
        result = executor.execute(self.request(single_model_option(), applicable=False))
        self.assertEqual(TerminalStatus.DEFERRED, result.status)
        self.assertEqual("inapplicable", result.result_code)
        self.assertEqual([], adapter.calls)
        self.assertEqual(Nanodollars(100), self.ledger.snapshot(self.budget_id).available)

    def test_missing_adapter_fails_before_spending(self):
        executor = self.make_executor({})
        with self.assertRaises(ExecutorConfigurationError):
            executor.execute(self.request(single_model_option()))
        self.assertEqual(Nanodollars(100), self.ledger.snapshot(self.budget_id).available)


if __name__ == "__main__":
    unittest.main()
