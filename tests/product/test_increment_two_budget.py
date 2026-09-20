from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import threading
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AccountId,
    AttemptId,
    AuthorizationId,
    BudgetId,
    CostEstimate,
    DecisionId,
    EstimateState,
    Nanodollars,
    RequestId,
    ReservationId,
)
from iceberg_router.core import (  # noqa: E402
    AdmissionDenied,
    AdmissionRequest,
    BoundUnavailable,
    BudgetContractBreach,
    BudgetGovernor,
    DuplicateConflict,
    InvalidTransition,
    ReservationState,
    SQLiteBudgetLedger,
)


class BudgetTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "ledger.sqlite3"
        self.ledger = SQLiteBudgetLedger(self.path)
        self.governor = BudgetGovernor(self.ledger)
        self.budget_id = BudgetId("budget-1")
        self.ledger.create_budget(self.budget_id, Nanodollars(100))

    def tearDown(self):
        self.temporary.cleanup()

    def admission(self, suffix: str, liability: int) -> AdmissionRequest:
        return AdmissionRequest(
            budget_id=self.budget_id,
            reservation_id=ReservationId(f"reservation-{suffix}"),
            request_id=RequestId(f"request-{suffix}"),
            decision_id=DecisionId(f"decision-{suffix}"),
            account_id=AccountId("model-serving"),
            upper_liability=CostEstimate(
                EstimateState.KNOWN, "bound-v1", Nanodollars(liability)
            ),
        )

    def authorize(self, suffix: str, liability: int = 60):
        return self.governor.authorize(
            self.admission(suffix, liability),
            authorization_id=AuthorizationId(f"authorization-{suffix}"),
            attempt_id=AttemptId(f"attempt-{suffix}"),
        )


class AdmissionTests(BudgetTestCase):
    def test_expected_cost_does_not_override_upper_liability(self):
        expected_cost = Nanodollars(1)
        self.assertLess(expected_cost, Nanodollars(101))
        with self.assertRaises(AdmissionDenied):
            self.governor.reserve(self.admission("too-large", 101))
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(0), snapshot.outstanding_liability)
        self.assertEqual(Nanodollars(100), snapshot.available)

    def test_unknown_upper_liability_fails_closed(self):
        request = AdmissionRequest(
            budget_id=self.budget_id,
            reservation_id=ReservationId("reservation-unknown"),
            request_id=RequestId("request-unknown"),
            decision_id=DecisionId("decision-unknown"),
            account_id=AccountId("model-serving"),
            upper_liability=CostEstimate(EstimateState.UNKNOWN, "bound-v1"),
        )
        with self.assertRaises(BoundUnavailable):
            self.governor.reserve(request)

    def test_exact_boundary_is_admitted_and_reservation_is_idempotent(self):
        request = self.admission("exact", 100)
        first = self.governor.reserve(request)
        second = self.governor.reserve(request)
        self.assertEqual(first, second)
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(100), snapshot.outstanding_liability)
        self.assertEqual(Nanodollars(0), snapshot.available)

    def test_conflicting_reservation_identity_is_rejected(self):
        request = self.admission("same", 20)
        self.governor.reserve(request)
        conflicting = AdmissionRequest(
            budget_id=request.budget_id,
            reservation_id=request.reservation_id,
            request_id=RequestId("request-different"),
            decision_id=request.decision_id,
            account_id=request.account_id,
            upper_liability=request.upper_liability,
        )
        with self.assertRaises(DuplicateConflict):
            self.governor.reserve(conflicting)

    def test_concurrent_reservations_cannot_double_spend(self):
        barrier = threading.Barrier(2)

        def reserve(suffix: str) -> str:
            ledger = SQLiteBudgetLedger(self.path)
            governor = BudgetGovernor(ledger)
            barrier.wait()
            try:
                governor.reserve(self.admission(suffix, 70))
            except AdmissionDenied:
                return "denied"
            return "admitted"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, ("concurrent-a", "concurrent-b")))
        self.assertCountEqual(["admitted", "denied"], results)
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(70), snapshot.outstanding_liability)
        self.assertEqual(Nanodollars(30), snapshot.available)


class AuthorizationTests(BudgetTestCase):
    def test_retry_attempt_needs_distinct_reservation_and_authorization(self):
        first = self.authorize("first", 30)
        self.assertEqual(AttemptId("attempt-first"), first.authorization.attempt_id)

        second_request = self.admission("retry", 30)
        with self.assertRaises(DuplicateConflict):
            self.governor.authorize(
                second_request,
                authorization_id=AuthorizationId("authorization-retry"),
                attempt_id=AttemptId("attempt-first"),
            )
        with self.assertRaises(InvalidTransition):
            self.ledger.get_reservation(second_request.reservation_id)

    def test_reservation_cannot_authorize_two_attempts(self):
        request = self.admission("single", 20)
        self.governor.authorize(
            request,
            authorization_id=AuthorizationId("authorization-one"),
            attempt_id=AttemptId("attempt-one"),
        )
        with self.assertRaises(DuplicateConflict):
            self.ledger.authorize_attempt(
                reservation_id=request.reservation_id,
                authorization_id=AuthorizationId("authorization-two"),
                attempt_id=AttemptId("attempt-two"),
            )

    def test_unreserved_attempt_cannot_be_authorized(self):
        with self.assertRaises(InvalidTransition):
            self.ledger.authorize_attempt(
                reservation_id=ReservationId("reservation-missing"),
                authorization_id=AuthorizationId("authorization-missing"),
                attempt_id=AttemptId("attempt-missing"),
            )


class SettlementTests(BudgetTestCase):
    def test_known_settlement_replaces_full_hold_with_actual(self):
        authorized = self.authorize("known", 60)
        result = self.ledger.settle(
            authorized.reservation.reservation_id,
            actual_cost=Nanodollars(25),
            idempotency_key="receipt-known",
        )
        self.assertFalse(result.idempotent_replay)
        self.assertEqual(ReservationState.SETTLED, result.reservation.state)
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(25), snapshot.confirmed_spend)
        self.assertEqual(Nanodollars(0), snapshot.outstanding_liability)
        self.assertEqual(Nanodollars(75), snapshot.available)

    def test_duplicate_settlement_is_idempotent_but_conflict_fails(self):
        authorized = self.authorize("duplicate", 60)
        reservation_id = authorized.reservation.reservation_id
        first = self.ledger.settle(
            reservation_id,
            actual_cost=Nanodollars(25),
            idempotency_key="receipt-duplicate",
        )
        replay = self.ledger.settle(
            reservation_id,
            actual_cost=Nanodollars(25),
            idempotency_key="receipt-duplicate",
        )
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(replay.idempotent_replay)
        with self.assertRaises(DuplicateConflict):
            self.ledger.settle(
                reservation_id,
                actual_cost=Nanodollars(26),
                idempotency_key="receipt-duplicate",
            )

    def test_unknown_usage_remains_pending_across_restart(self):
        authorized = self.authorize("pending", 60)
        reservation_id = authorized.reservation.reservation_id
        result = self.ledger.mark_pending(
            reservation_id, idempotency_key="pending-provider-usage"
        )
        self.assertEqual(ReservationState.PENDING, result.reservation.state)
        before = self.ledger.snapshot(self.budget_id)
        self.assertEqual(Nanodollars(60), before.outstanding_liability)

        reopened = SQLiteBudgetLedger(self.path)
        after = reopened.snapshot(self.budget_id)
        self.assertEqual(before, after)
        self.assertEqual(
            ReservationState.PENDING, reopened.get_reservation(reservation_id).state
        )

    def test_pending_usage_can_be_reconciled_idempotently(self):
        authorized = self.authorize("reconcile", 60)
        reservation_id = authorized.reservation.reservation_id
        self.ledger.mark_pending(reservation_id, idempotency_key="pending-reconcile")
        settled = self.ledger.settle(
            reservation_id,
            actual_cost=Nanodollars(40),
            idempotency_key="receipt-reconcile",
        )
        self.assertEqual(ReservationState.SETTLED, settled.reservation.state)
        self.assertEqual(Nanodollars(40), self.ledger.snapshot(self.budget_id).confirmed_spend)

        other = self.authorize("other", 10)
        with self.assertRaises(DuplicateConflict):
            self.ledger.mark_pending(
                other.reservation.reservation_id,
                idempotency_key="pending-reconcile",
            )

    def test_settlement_requires_an_authorized_attempt(self):
        reservation = self.governor.reserve(self.admission("no-attempt", 20))
        with self.assertRaises(InvalidTransition):
            self.ledger.settle(
                reservation.reservation_id,
                actual_cost=Nanodollars(10),
                idempotency_key="receipt-no-attempt",
            )

    def test_bound_breach_is_recorded_and_halts_admission(self):
        authorized = self.authorize("breach", 20)
        with self.assertRaises(BudgetContractBreach):
            self.ledger.settle(
                authorized.reservation.reservation_id,
                actual_cost=Nanodollars(30),
                idempotency_key="receipt-breach",
            )
        reservation = self.ledger.get_reservation(authorized.reservation.reservation_id)
        self.assertEqual(ReservationState.BREACHED, reservation.state)
        self.assertEqual(Nanodollars(30), reservation.actual_cost)
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertTrue(snapshot.halted)
        self.assertEqual(Nanodollars(30), snapshot.confirmed_spend)
        with self.assertRaises(AdmissionDenied):
            self.governor.reserve(self.admission("after-breach", 1))


if __name__ == "__main__":
    unittest.main()
