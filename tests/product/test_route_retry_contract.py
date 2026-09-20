"""Public retry regressions, intentionally separate from journal identity tests."""

from pathlib import Path
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.adapters import SingleAttemptAdapter  # noqa: E402
from iceberg_router.contracts import (  # noqa: E402
    BranchOutcome,
    BudgetId,
    Nanodollars,
    OperationKind,
    OperationResult,
    OptionId,
    PolicyVersion,
    UsageState,
)
from iceberg_router.core import (  # noqa: E402
    BudgetGovernor,
    IcebergRouter,
    OptionExecutor,
    RouteRequest,
    SQLiteAuditJournal,
    SQLiteBudgetLedger,
)
from iceberg_router.policies import FixedPolicy  # noqa: E402
from iceberg_router.testing import DeterministicIdentityFactory, FixedClock  # noqa: E402
from tests.product.test_increment_eight_router import (  # noqa: E402
    candidate,
    policy_request,
    validated_option,
)


class RouteRetryContractTests(unittest.TestCase):
    def test_identical_completed_retry_returns_recorded_result_without_second_call(self):
        """Identical public retries return the durable completion."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = SQLiteBudgetLedger(root / "ledger.sqlite3")
            journal = SQLiteAuditJournal(root / "journal.sqlite3")
            budget_id = BudgetId("budget-1")
            ledger.create_budget(budget_id, Nanodollars(100))
            identities = DeterministicIdentityFactory()
            calls = []

            def transport(context):
                calls.append(context)
                return OperationResult(
                    BranchOutcome.SUCCESS,
                    UsageState.KNOWN,
                    Nanodollars(7),
                    "output-1",
                    "receipt-1",
                )

            executor = OptionExecutor(
                BudgetGovernor(ledger),
                {
                    OperationKind.MODEL_CALL: SingleAttemptAdapter(
                        OperationKind.MODEL_CALL, "operation-v1", transport
                    )
                },
                identity_factory=identities,
                clock=FixedClock("2026-09-19T12:00:00Z"),
            )
            router = IcebergRouter(
                FixedPolicy(OptionId("small"), PolicyVersion("fixed-v1")),
                executor,
                journal,
                identity_factory=identities,
                clock=FixedClock("2026-09-19T12:00:00Z"),
            )
            request = RouteRequest(
                policy_request(candidate()),
                budget_id,
                {OptionId("small"): validated_option()},
            )

            first = router.route(request)
            replay = router.route(request)

            self.assertEqual(replay, first)
            self.assertEqual(len(calls), 1)
            self.assertEqual(ledger.snapshot(budget_id).confirmed_spend, Nanodollars(7))


if __name__ == "__main__":
    unittest.main()
