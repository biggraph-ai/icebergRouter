"""PR 8 controlled evidence-acquisition acceptance tests."""

from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import AccountId, BudgetId, Nanodollars, OptionId, RequestId  # noqa: E402
from iceberg_router.core import (  # noqa: E402
    FrozenStrataEstimator, OutcomeCostObservation, ProbeCandidate, ProbeVariant,
    SQLiteBudgetLedger, authorize_probe_plan, plan_probes,
)
from iceberg_router.experiments.evidence import run_evidence_study  # noqa: E402


class StatisticsTests(unittest.TestCase):
    def test_intrinsic_variability_and_estimation_uncertainty_are_distinct(self):
        rows = tuple(
            OutcomeCostObservation("math", OptionId("option-a"), value, Nanodollars(cost))
            for value, cost in ((True, 3), (False, 4), (True, 4), (False, 5))
        )
        estimate = FrozenStrataEstimator(rows, version="v1").estimate(
            "math", OptionId("option-a")
        )
        self.assertEqual(estimate.success_probability, Decimal("0.5"))
        self.assertEqual(estimate.intrinsic_variance, Decimal("0.25"))
        self.assertEqual(estimate.probability_standard_error, Decimal("0.25"))
        self.assertEqual(estimate.mean_cost, Nanodollars(4))

    def test_updates_are_immutable_and_versioned(self):
        first = OutcomeCostObservation("math", OptionId("option-a"), True, Nanodollars(2))
        original = FrozenStrataEstimator((first,), version="v1")
        updated = original.updated((first,), version="v2")
        self.assertEqual(original.estimate("math", OptionId("option-a")).observations, 1)
        self.assertEqual(updated.estimate("math", OptionId("option-a")).observations, 2)


class ProbePlanningTests(unittest.TestCase):
    def candidates(self):
        return tuple(
            ProbeCandidate(RequestId(f"request-{number}"), "math" if number % 2 else "doc",
                           OptionId(f"option-{number % 3}"), Nanodollars(4), number)
            for number in range(1, 9)
        )

    def test_all_variants_are_deterministic_and_cash_capped(self):
        for variant in ProbeVariant:
            first = plan_probes(variant, self.candidates(), cap=Nanodollars(12), seed="seed")
            second = plan_probes(variant, self.candidates(), cap=Nanodollars(12), seed="seed")
            self.assertEqual(first, second)
            self.assertLessEqual(first.reserved, first.cap)
        self.assertEqual(
            plan_probes(ProbeVariant.ZERO, self.candidates(), cap=Nanodollars(12), seed="seed").selected,
            (),
        )

    def test_racing_does_not_irreversibly_prune_an_option(self):
        plan = plan_probes(
            ProbeVariant.RESOURCE_AWARE_RACING, self.candidates(),
            cap=Nanodollars(32), seed="seed",
        )
        self.assertEqual({row.option_id for row in plan.selected},
                         {OptionId("option-0"), OptionId("option-1"), OptionId("option-2")})

    def test_plan_is_authorized_transactionally_under_adaptation_subbudget(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteBudgetLedger(Path(directory) / "ledger.sqlite3")
            budget, account = BudgetId("experiment"), AccountId("adaptation")
            ledger.create_budget(budget, Nanodollars(100))
            ledger.set_account_budget(budget, account, Nanodollars(12))
            plan = plan_probes(ProbeVariant.STRATIFIED, self.candidates(),
                               cap=Nanodollars(12), seed="seed")
            records = authorize_probe_plan(ledger, plan, budget_id=budget, account_id=account)
            self.assertEqual(len(records), 3)
            self.assertEqual(ledger.account_snapshot(budget, account).available, Nanodollars(0))


class ControlledStudyTests(unittest.TestCase):
    def test_variants_hold_allocator_information_and_coverage_contracts_fixed(self):
        report = run_evidence_study()
        self.assertTrue(report["downstreamAllocatorHeldConstant"])
        self.assertTrue(report["matchedCoverage"])
        self.assertEqual(set(report["variants"]), {variant.value for variant in ProbeVariant})
        for item in report["variants"].values():
            self.assertLessEqual(int(item["probeReservedNanos"]),
                                 int(item["predeclaredProbeCapNanos"]))
            self.assertIn("intrinsicOutcomeVariance", item)
            self.assertIn("estimatedProbabilityStandardError", item)

    def test_honest_null_result_simplifies_instead_of_claiming_advantage(self):
        report = run_evidence_study()
        self.assertFalse(report["evidenceAcquisitionRepaidCost"])
        self.assertEqual(report["stopRuleConclusion"], "null-result-simplify-to-zero-probe")
        self.assertFalse(any(report["claims"].values()))
        zero = int(report["variants"][ProbeVariant.ZERO.value]["netUtilityNanos"])
        for variant, item in report["variants"].items():
            if variant != ProbeVariant.ZERO.value:
                self.assertLessEqual(int(item["netUtilityNanos"]), zero)

    def test_tampered_study_input_is_rejected_by_provenance(self):
        import tempfile
        from iceberg_router.experiments.evidence import DEFAULT_FIXTURE
        with tempfile.TemporaryDirectory() as directory:
            altered = json.loads(DEFAULT_FIXTURE.read_text())
            altered["notice"] = "changed"
            path = Path(directory) / "workload.json"
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "provenance"):
                run_evidence_study(fixture_path=path)


if __name__ == "__main__":
    unittest.main()
