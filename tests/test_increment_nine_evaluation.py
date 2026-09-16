from pathlib import Path
import sys
import unittest


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    CheckerResult,
    DecisionId,
    Nanodollars,
    ObjectiveResult,
    OptionId,
    RequestId,
    UserVote,
)
from iceberg_router.evaluation import (  # noqa: E402
    EvaluationError,
    EvaluationObservation,
    EvidenceKind,
    ExactRate,
    ServiceOutcome,
    summarize,
)


def observation(
    number: int,
    outcome: ServiceOutcome = ServiceOutcome.SERVED,
    *,
    evidence: EvidenceKind = EvidenceKind.EXECUTED,
    option: str | None = "small",
    cost: int = 5,
    unknown: int = 0,
    user_vote: UserVote = UserVote.MISSING,
    objective: ObjectiveResult = ObjectiveResult.UNKNOWN,
    checker: CheckerResult = CheckerResult.NOT_RUN,
) -> EvaluationObservation:
    return EvaluationObservation(
        RequestId(f"request-{number}"),
        DecisionId(f"decision-{number}"),
        evidence,
        outcome,
        None if option is None else OptionId(option),
        Nanodollars(cost),
        unknown,
        user_vote,
        objective,
        checker,
    )


class EvaluationTests(unittest.TestCase):
    def test_coverage_uses_original_workload_denominator(self):
        summary = summarize(
            (
                observation(1),
                observation(2, ServiceOutcome.DEFERRED, option=None, cost=0),
                observation(3, ServiceOutcome.FAILED, option="large", cost=7),
                observation(4, ServiceOutcome.PENDING, unknown=1, cost=2),
            )
        )
        self.assertEqual(summary.original_workload_size, 4)
        self.assertEqual(summary.coverage, ExactRate(1, 4))
        self.assertEqual(summary.deferral_rate, ExactRate(1, 4))
        self.assertEqual(summary.known_cost, Nanodollars(14))
        self.assertEqual(summary.unknown_cost_attempts, 1)

    def test_missing_feedback_is_not_acceptance(self):
        summary = summarize((observation(1), observation(2)))
        self.assertEqual(summary.user_vote_counts[UserVote.MISSING], 2)
        self.assertEqual(summary.user_vote_counts[UserVote.ACCEPT], 0)
        self.assertEqual(summary.objective_counts[ObjectiveResult.UNKNOWN], 2)

    def test_feedback_channels_remain_independent(self):
        summary = summarize(
            (
                observation(
                    1,
                    user_vote=UserVote.ACCEPT,
                    objective=ObjectiveResult.FAIL,
                    checker=CheckerResult.PASS,
                ),
            )
        )
        self.assertEqual(summary.user_vote_counts[UserVote.ACCEPT], 1)
        self.assertEqual(summary.objective_counts[ObjectiveResult.FAIL], 1)
        self.assertEqual(summary.checker_counts[CheckerResult.PASS], 1)

    def test_unknown_cost_is_not_coerced_to_zero(self):
        summary = summarize(
            (observation(1, ServiceOutcome.PENDING, cost=3, unknown=2),)
        )
        self.assertEqual(summary.known_cost, Nanodollars(3))
        self.assertEqual(summary.unknown_cost_attempts, 2)
        with self.assertRaises(ValueError):
            observation(1, ServiceOutcome.PENDING, unknown=0)

    def test_executed_and_synthetic_evidence_cannot_be_spliced(self):
        with self.assertRaises(EvaluationError):
            summarize(
                (
                    observation(1),
                    observation(2, evidence=EvidenceKind.SYNTHETIC),
                )
            )

    def test_duplicate_requests_or_decisions_are_rejected(self):
        first = observation(1)
        with self.assertRaises(EvaluationError):
            summarize((first, first))
        duplicate_decision = EvaluationObservation(
            RequestId("request-2"),
            first.decision_id,
            first.evidence_kind,
            first.service_outcome,
            first.selected_option_id,
            first.known_cost,
            0,
        )
        with self.assertRaises(EvaluationError):
            summarize((first, duplicate_decision))

    def test_selection_counts_include_failed_and_pending_rows(self):
        summary = summarize(
            (
                observation(1, option="small"),
                observation(2, ServiceOutcome.FAILED, option="small"),
                observation(3, ServiceOutcome.PENDING, option="large", unknown=1),
                observation(4, ServiceOutcome.DEFERRED, option=None, cost=0),
            )
        )
        self.assertEqual(summary.selection_counts[OptionId("small")], 2)
        self.assertEqual(summary.selection_counts[OptionId("large")], 1)

    def test_summary_json_uses_integer_string_money_and_exact_rates(self):
        wire = summarize((observation(1, cost=9),)).to_json()
        self.assertEqual(wire["knownCostNanos"], "9")
        self.assertEqual(wire["coverage"], {"numerator": 1, "denominator": 1})
        self.assertNotIsInstance(wire["knownCostNanos"], float)

    def test_summary_mappings_are_immutable(self):
        summary = summarize((observation(1),))
        with self.assertRaises(TypeError):
            summary.service_counts[ServiceOutcome.SERVED] = 0
        with self.assertRaises(TypeError):
            summary.selection_counts[OptionId("large")] = 1

    def test_empty_or_invalid_tables_are_rejected(self):
        with self.assertRaises(EvaluationError):
            summarize(())
        with self.assertRaises(TypeError):
            summarize(("not-an-observation",))
        with self.assertRaises(ValueError):
            ExactRate(2, 1)


if __name__ == "__main__":
    unittest.main()
