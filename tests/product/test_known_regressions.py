"""Accepted enhancement regressions with explicit owning PRs.

These tests are kept separate from the original current-behavior suites so no
existing invariant is weakened when an owning PR changes behavior deliberately.
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
    MODEL_RESOURCE,
    OperationKind,
    single_model_option,
)


class FinancialTruthRegressions(unittest.TestCase):
    def test_invalid_semantic_outcome_preserves_and_records_known_over_bound_invoice(self):
        """PR 1 regression: semantic invalidity cannot erase invoice truth."""
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
                {MODEL_RESOURCE: adapter},
                identity_factory=DeterministicIdentityFactory(),
                clock=FixedClock("2026-09-19T12:00:00Z"),
            )
            result = executor.execute(
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
            self.assertEqual(result.result_code, "budget_contract_breach")
            self.assertEqual(result.attempts[0].result.actual_cost, Nanodollars(20))
            self.assertEqual(
                result.attempts[0].result.provider_receipt, "receipt-over-bound"
            )
            self.assertEqual(result.attempts[0].result.usage_state, UsageState.KNOWN)
            self.assertIn(
                "invalid_outcome", {event.kind.value for event in result.trace}
            )

    def test_halt_blocks_new_authorization_on_preexisting_held_reservation(self):
        """PR 1 regression: halt closes both attempt-authorization entry points."""
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
            held_combined = ReservationId("held-combined-before-breach")
            ledger.reserve(
                budget_id=budget_id,
                reservation_id=held_combined,
                request_id=RequestId("request-held-combined"),
                decision_id=DecisionId("decision-held-combined"),
                account_id=AccountId("serving"),
                max_liability=Nanodollars(5),
            )
            replay_reservation = ReservationId("authorized-before-breach")
            replay_authorization = AuthorizationId("authorization-before-breach")
            replay_attempt = AttemptId("attempt-before-breach")
            replay_records = ledger.reserve_and_authorize(
                budget_id=budget_id,
                reservation_id=replay_reservation,
                request_id=RequestId("request-authorized"),
                decision_id=DecisionId("decision-authorized"),
                account_id=AccountId("serving"),
                max_liability=Nanodollars(5),
                authorization_id=replay_authorization,
                attempt_id=replay_attempt,
            )
            separate_replay_reservation = ReservationId(
                "separate-authorized-before-breach"
            )
            ledger.reserve(
                budget_id=budget_id,
                reservation_id=separate_replay_reservation,
                request_id=RequestId("request-separate-authorized"),
                decision_id=DecisionId("decision-separate-authorized"),
                account_id=AccountId("serving"),
                max_liability=Nanodollars(5),
            )
            separate_replay_authorization = AuthorizationId(
                "separate-authorization-before-breach"
            )
            separate_replay_attempt = AttemptId("separate-attempt-before-breach")
            separate_replay_record = ledger.authorize_attempt(
                reservation_id=separate_replay_reservation,
                authorization_id=separate_replay_authorization,
                attempt_id=separate_replay_attempt,
            )
            pending_reservation = ReservationId("pending-before-breach")
            ledger.reserve_and_authorize(
                budget_id=budget_id,
                reservation_id=pending_reservation,
                request_id=RequestId("request-pending"),
                decision_id=DecisionId("decision-pending"),
                account_id=AccountId("serving"),
                max_liability=Nanodollars(5),
                authorization_id=AuthorizationId("authorization-pending"),
                attempt_id=AttemptId("attempt-pending"),
            )
            ledger.mark_pending(pending_reservation, idempotency_key="pending:unknown")
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
            with self.assertRaises(AdmissionDenied):
                ledger.reserve_and_authorize(
                    budget_id=budget_id,
                    reservation_id=held_combined,
                    request_id=RequestId("request-held-combined"),
                    decision_id=DecisionId("decision-held-combined"),
                    account_id=AccountId("serving"),
                    max_liability=Nanodollars(5),
                    authorization_id=AuthorizationId("combined-after-halt"),
                    attempt_id=AttemptId("combined-attempt-after-halt"),
                )
            self.assertEqual(
                ledger.reserve_and_authorize(
                    budget_id=budget_id,
                    reservation_id=replay_reservation,
                    request_id=RequestId("request-authorized"),
                    decision_id=DecisionId("decision-authorized"),
                    account_id=AccountId("serving"),
                    max_liability=Nanodollars(5),
                    authorization_id=replay_authorization,
                    attempt_id=replay_attempt,
                ),
                replay_records,
            )
            self.assertEqual(
                ledger.authorize_attempt(
                    reservation_id=separate_replay_reservation,
                    authorization_id=separate_replay_authorization,
                    attempt_id=separate_replay_attempt,
                ),
                separate_replay_record,
            )
            reconciled = ledger.settle(
                pending_reservation,
                actual_cost=Nanodollars(3),
                idempotency_key="reconcile:pending",
            )
            self.assertEqual(reconciled.reservation.actual_cost, Nanodollars(3))
            replay_settlement = ledger.settle(
                breached,
                actual_cost=Nanodollars(20),
                idempotency_key="settle:breach",
            )
            self.assertTrue(replay_settlement.idempotent_replay)


if __name__ == "__main__":
    unittest.main()
