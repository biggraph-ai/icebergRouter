"""PR 6 leakage isolation, workload completeness, and subbudget tests."""

from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AccountId, AttemptId, AuthorizationId, BudgetId, DecisionId, FeedbackChannel,
    Nanodollars, RequestId, ReservationId, TaskFeatures,
)
from iceberg_router.core import (  # noqa: E402
    AdmissionDenied, BlindEvaluationCapability, JournalFeedbackStore,
    SQLiteAuditJournal, SQLiteBudgetLedger,
)
from iceberg_router.evaluation import (  # noqa: E402
    EvaluationError, EvidenceKind, MissingResultMode, ServiceOutcome,
    TraceEvidenceKind, WorkloadManifest, WorkloadManifestEntry, WorkloadSplit,
    summarize, summarize_manifest,
)
from tests.product.test_increment_nine_evaluation import observation  # noqa: E402
from tests.product.test_increment_six_policies import candidate, request  # noqa: E402
from tests.product.test_increment_ten_feedback_store import feedback  # noqa: E402


class FeedbackIsolationTests(unittest.TestCase):
    def test_learning_view_cannot_read_blind_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            capability = BlindEvaluationCapability()
            store = JournalFeedbackStore(
                SQLiteAuditJournal(Path(directory) / "journal.sqlite3"),
                blind_capability=capability,
            )
            training = replace(feedback(1), channel=FeedbackChannel.TRAINING_LABEL)
            blind = replace(feedback(2), channel=FeedbackChannel.BLIND_EVALUATION)
            store.append_training_label(training)
            store.append_blind_evaluation(blind, capability)
            learning = store.learning_view().snapshot("2026-09-16T12:00:00Z")
            self.assertEqual(learning.events, (training,))
            self.assertEqual(
                store.training_label_view()
                .snapshot("2026-09-16T12:00:00Z")
                .events,
                (training,),
            )
            self.assertEqual(
                store.operational_checker_view()
                .snapshot("2026-09-16T12:00:00Z")
                .events,
                (),
            )
            with self.assertRaises(PermissionError):
                store.blind_evaluation_view(BlindEvaluationCapability())
            final = store.blind_evaluation_view(capability).snapshot(
                "2026-09-16T12:00:00Z"
            )
            self.assertEqual(final.events, (blind,))


class ManifestAccountingTests(unittest.TestCase):
    def manifest(self):
        policy_request = request(candidate("small"))
        return WorkloadManifest(
            "manifest-v1",
            policy_request.configuration_snapshot,
            tuple(
                WorkloadManifestEntry(
                    RequestId(f"request-{number}"),
                    WorkloadSplit.FINAL_EVALUATION,
                    TaskFeatures("document", (), "features-v1"),
                )
                for number in range(1, 5)
            ),
        )

    def test_manifest_preserves_four_request_denominator_with_three_results(self):
        summary = summarize_manifest(
            self.manifest(), (observation(1), observation(2), observation(3))
        )
        self.assertEqual(summary.original_workload_size, 4)
        self.assertEqual(summary.service_counts[ServiceOutcome.MISSING], 1)
        with self.assertRaisesRegex(EvaluationError, "incomplete"):
            summarize_manifest(
                self.manifest(),
                (observation(1), observation(2), observation(3)),
                mode=MissingResultMode.ERROR,
            )

    def test_duplicate_final_utility_for_request_is_rejected(self):
        served = replace(observation(1), final_utility=1)
        with self.assertRaisesRegex(EvaluationError, "duplicate final utility"):
            summarize_manifest(self.manifest(), (served, served))

    def test_blind_and_training_costs_are_disclosed_but_not_serving_cost(self):
        summary = summarize(
            (observation(1, cost=5),),
            blind_scoring_cost=Nanodollars(7),
            training_cost=Nanodollars(3),
        )
        self.assertEqual(summary.known_cost, Nanodollars(5))
        self.assertEqual(summary.to_json()["blindScoringCostNanos"], "7")
        self.assertEqual(summary.to_json()["trainingCostNanos"], "3")

    def test_single_call_matrix_cannot_claim_executed_workflow_evidence(self):
        with self.assertRaisesRegex(ValueError, "single-call matrices"):
            replace(
                observation(1, evidence=EvidenceKind.EXECUTED),
                trace_evidence=TraceEvidenceKind.SINGLE_CALL_MATRIX,
            )


class SubbudgetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = SQLiteBudgetLedger(
            Path(self.temporary.name) / "ledger.sqlite3"
        )
        self.budget = BudgetId("budget-1")
        self.ledger.create_budget(self.budget, Nanodollars(100))

    def spend(self, number: int, account: str, bound: int, actual: int):
        reservation = ReservationId(f"reservation-{number}")
        self.ledger.reserve_and_authorize(
            budget_id=self.budget,
            reservation_id=reservation,
            request_id=RequestId(f"request-{number}"),
            decision_id=DecisionId(f"decision-{number}"),
            account_id=AccountId(account),
            max_liability=Nanodollars(bound),
            authorization_id=AuthorizationId(f"authorization-{number}"),
            attempt_id=AttemptId(f"attempt-{number}"),
        )
        self.ledger.settle(
            reservation,
            actual_cost=Nanodollars(actual),
            idempotency_key=f"settle:{number}",
        )

    def test_adaptation_cap_stops_probes_while_serving_funds_remain(self):
        adaptation = AccountId("adaptation")
        serving = AccountId("serving")
        self.ledger.set_account_budget(self.budget, adaptation, Nanodollars(5))
        self.ledger.set_account_budget(self.budget, serving, Nanodollars(80))
        self.spend(1, "adaptation", 5, 5)
        with self.assertRaisesRegex(AdmissionDenied, "subbudget"):
            self.spend(2, "adaptation", 1, 1)
        self.spend(3, "serving", 20, 10)
        self.assertEqual(
            self.ledger.account_snapshot(self.budget, adaptation).available,
            Nanodollars(0),
        )
        self.assertEqual(
            self.ledger.account_snapshot(self.budget, serving).available,
            Nanodollars(70),
        )

    def test_every_decision_informing_account_appears_in_totals(self):
        accounts = ("probe", "feature", "operational-checker", "serving", "audit")
        for number, account in enumerate(accounts, start=1):
            self.spend(number, account, 5, number)
        totals = self.ledger.account_totals(self.budget)
        self.assertEqual(set(totals), {AccountId(account) for account in accounts})
        self.assertEqual(sum(value.value for value in totals.values()), 15)


if __name__ == "__main__":
    unittest.main()
