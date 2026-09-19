"""Accepted enhancement regressions that remain owned expected failures.

These tests must become ordinary passing tests in their owning PRs. They are kept
separate from the current-behavior suites so no existing invariant is weakened.
"""

from pathlib import Path
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AccountId,
    AttemptId,
    AuthorizationId,
    BranchOutcome,
    BudgetId,
    DecisionId,
    Nanodollars,
    RequestId,
    ReservationId,
    UsageState,
)
from iceberg_router.core import (  # noqa: E402
    AdmissionDenied,
    BudgetContractBreach,
    BudgetGovernor,
    OperationResult,
    OptionExecutor,
    SQLiteBudgetLedger,
)
from iceberg_router.testing import (  # noqa: E402
    DeterministicIdentityFactory,
    FixedClock,
    ScriptedAdapter,
)
from tests.product.test_increment_four_executor import (  # noqa: E402
    ExecutionRequest,
    OperationKind,
    single_model_option,
)


class FinancialTruthKnownFailures(unittest.TestCase):
    @unittest.expectedFailure
    def test_invalid_semantic_outcome_preserves_and_records_known_over_bound_invoice(self):
        """Owned by enhancement PR 1."""
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget_id = BudgetId("budget-1")
            ledger.create_budget(budget_id, Nanodollars(100))
            adapter = ScriptedAdapter(
                (
                    OperationResult(
                        BranchOutcome.PASS,
                        UsageState.KNOWN,
                        Nanodollars(20),
                        "invalid-content",
                        "receipt-over-bound",
                    ),
                )
            )
            executor = OptionExecutor(
                BudgetGovernor(ledger),
                {OperationKind.MODEL_CALL: adapter},
                identity_factory=DeterministicIdentityFactory(),
                clock=FixedClock("2026-09-19T12:00:00Z"),
            )
            executor.execute(
                ExecutionRequest(
                    RequestId("request-1"),
                    DecisionId("decision-1"),
                    budget_id,
                    single_model_option(liability=5),
                    True,
                )
            )
            snapshot = ledger.snapshot(budget_id)
            self.assertEqual(snapshot.confirmed_spend, Nanodollars(20))
            self.assertTrue(snapshot.halted)

    @unittest.expectedFailure
    def test_halt_blocks_new_authorization_on_preexisting_held_reservation(self):
        """Owned by enhancement PR 1."""
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget_id = BudgetId("budget-1")
            ledger.create_budget(budget_id, Nanodollars(100))
            held = ReservationId("held-before-breach")
            ledger.reserve(
                budget_id=budget_id,
                reservation_id=held,
                request_id=RequestId("request-held"),
                decision_id=DecisionId("decision-held"),
                account_id=AccountId("serving"),
                max_liability=Nanodollars(5),
            )
            breached = ReservationId("breached-reservation")
            ledger.reserve_and_authorize(
                budget_id=budget_id,
                reservation_id=breached,
                request_id=RequestId("request-breach"),
                decision_id=DecisionId("decision-breach"),
                account_id=AccountId("serving"),
                max_liability=Nanodollars(5),
                authorization_id=AuthorizationId("authorization-breach"),
                attempt_id=AttemptId("attempt-breach"),
            )
            with self.assertRaises(BudgetContractBreach):
                ledger.settle(
                    breached,
                    actual_cost=Nanodollars(20),
                    idempotency_key="settle:breach",
                )
            with self.assertRaises(AdmissionDenied):
                ledger.authorize_attempt(
                    reservation_id=held,
                    authorization_id=AuthorizationId("authorization-after-halt"),
                    attempt_id=AttemptId("attempt-after-halt"),
                )


if __name__ == "__main__":
    unittest.main()
