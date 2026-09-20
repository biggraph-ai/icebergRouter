"""PR 3 durable ownership, replay, outbox, and recovery acceptance tests."""

from pathlib import Path
import sys
import tempfile
import threading
import unittest

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.adapters import SingleAttemptAdapter  # noqa: E402
from iceberg_router.contracts import (  # noqa: E402
    BranchOutcome, BudgetId, Nanodollars, OperationKind, OperationResult,
    OptionId, PolicyVersion, UsageState,
)
from iceberg_router.core import (  # noqa: E402
    BudgetGovernor, ExecutionConflict, IcebergRouter, OptionExecutor, RouteRequest,
    RouteState, SQLiteAuditJournal, SQLiteBudgetLedger, SQLiteExecutionStore,
)
from iceberg_router.policies import FixedPolicy  # noqa: E402
from iceberg_router.testing import FixedClock  # noqa: E402
from tests.product.test_increment_eight_router import (  # noqa: E402
    MODEL_RESOURCE, candidate, policy_request, validated_option,
)
from tests.product.test_increment_four_executor import repair_option  # noqa: E402


class DurableRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ledger = SQLiteBudgetLedger(self.root / "ledger.sqlite3")
        self.journal = SQLiteAuditJournal(self.root / "journal.sqlite3")
        self.store = SQLiteExecutionStore(self.root / "executions.sqlite3")
        self.budget = BudgetId("budget-1")
        self.ledger.create_budget(self.budget, Nanodollars(100))

    def router(self, transport, *, verify=None):
        adapters = {
            MODEL_RESOURCE: SingleAttemptAdapter(
                OperationKind.MODEL_CALL, "operation-v1", MODEL_RESOURCE, transport
            )
        }
        if verify is not None:
            adapters[OperationKind.VERIFY] = verify
        return IcebergRouter(
            FixedPolicy(OptionId("small"), PolicyVersion("fixed-v1")),
            OptionExecutor(BudgetGovernor(self.ledger), adapters),
            self.journal,
            clock=FixedClock("2026-09-20T12:00:00Z"),
            execution_store=self.store,
        )

    def request(self, payload=None):
        return RouteRequest(
            policy_request(candidate()), self.budget,
            {OptionId("small"): validated_option()}, payload,
        )

    def test_concurrent_duplicates_have_one_owner(self):
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def transport(context):
            calls.append(context)
            entered.set()
            release.wait(5)
            return OperationResult(
                BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(2), "answer"
            )

        router = self.router(transport)
        results = []
        thread = threading.Thread(target=lambda: results.append(router.route(self.request())))
        thread.start()
        self.assertTrue(entered.wait(5))
        duplicate = router.route(self.request())
        self.assertEqual(duplicate.state, RouteState.IN_PROGRESS)
        release.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(calls), 1)
        self.assertEqual(results[0].state, RouteState.COMPLETED)

    def test_conflicting_content_fails_before_authorization(self):
        calls = []

        def transport(context):
            calls.append(context)
            return OperationResult(
                BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(1), "answer"
            )

        router = self.router(transport)
        router.route(self.request({"prompt": "first"}))
        outbox_count = len(self.ledger.outbox_events())
        with self.assertRaises(ExecutionConflict):
            router.route(self.request({"prompt": "changed"}))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger.outbox_events()), outbox_count)

    def test_completed_result_replays_after_router_restart(self):
        calls = []

        def transport(context):
            calls.append(context)
            return OperationResult(
                BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(3),
                "answer", "receipt-1",
            )

        first = self.router(transport).route(self.request())
        restarted = self.router(transport).route(self.request())
        self.assertEqual(restarted, first)
        self.assertEqual(len(calls), 1)

    def test_crash_state_retains_artifact_and_unresolved_dispatch_without_redispatch(self):
        model_calls = []
        checker_calls = []

        class CrashingChecker:
            def execute(self, context):
                checker_calls.append(context)
                raise SystemExit("synthetic process crash")

        class Models:
            def execute(self, context):
                model_calls.append(context)
                return OperationResult(
                    BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(2), "draft-ref"
                )

        executor = OptionExecutor(
            BudgetGovernor(self.ledger),
            {
                repair_option().definition.nodes[0].resource: Models(),
                repair_option().definition.nodes[1].resource: CrashingChecker(),
            },
        )
        router = IcebergRouter(
            FixedPolicy(OptionId("test-option"), PolicyVersion("fixed-v1")),
            executor, self.journal, execution_store=self.store,
        )
        request = RouteRequest(
            policy_request(candidate("test-option", bound=53)), self.budget,
            {OptionId("test-option"): repair_option()}, {"prompt": "draft"},
        )
        with self.assertRaises(SystemExit):
            router.route(request)
        transitions = self.store.transitions(request.policy_request.request_id)
        self.assertTrue(any(
            kind == "artifact_stored" and payload.get("reference") == "draft-ref"
            for kind, payload in transitions
        ))
        self.assertTrue(any(
            kind == "dispatched_unknown" and payload.get("nodeId") == "verify"
            for kind, payload in transitions
        ))
        replay = router.route(request)
        self.assertEqual(replay.state, RouteState.UNKNOWN)
        self.assertEqual(len(model_calls), 1)
        self.assertEqual(len(checker_calls), 1)
        self.assertGreater(self.ledger.snapshot(self.budget).outstanding_liability.value, 0)

    def test_ledger_outbox_is_idempotent_with_ledger_replay(self):
        self.router(lambda context: OperationResult(
            BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(4), "answer"
        )).route(self.request())
        events = self.ledger.outbox_events()
        self.assertEqual([event["eventKind"] for event in events], ["authorization", "settlement"])
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
