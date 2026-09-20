from dataclasses import FrozenInstanceError
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AttemptId,
    AuthorizationId,
    CandidateDecision,
    CheckerResult,
    CostEstimate,
    DecisionId,
    DecisionRecord,
    EstimateState,
    EvaluatorVersion,
    EventId,
    FeedbackEvent,
    MAX_NANODOLLARS,
    Nanodollars,
    ObjectiveResult,
    OptionId,
    OutputId,
    PolicyVersion,
    Probability,
    RequestId,
    ReservationId,
    Score,
    SnapshotVersion,
    TraceEvent,
    TraceEventKind,
    UsageEvent,
    UsageState,
    UserVote,
    WorkloadId,
    checked_sum,
)


def known_cost(value: int, version: str = "tariff-v1") -> CostEstimate:
    return CostEstimate(EstimateState.KNOWN, version, Nanodollars(value))


def candidate(name: str = "cheap-v1", *, eligible: bool = True) -> CandidateDecision:
    return CandidateDecision(
        option_id=OptionId(name),
        eligible=eligible,
        eligibility_reasons=("applicable" if eligible else "privacy_blocked",),
        score=Score(Decimal("0.75"), "predicted_terminal_utility", "cal-v1"),
        expected_cost=known_cost(10),
        upper_liability=known_cost(20, "bound-v1"),
    )


class MoneyTests(unittest.TestCase):
    def test_json_round_trip_uses_decimal_strings(self):
        for value in (0, 1, 10**9, MAX_NANODOLLARS):
            with self.subTest(value=value):
                money = Nanodollars(value)
                self.assertEqual(str(value), money.to_json())
                self.assertEqual(money, Nanodollars.from_json(money.to_json()))
                self.assertIsInstance(json.dumps(money.to_json()), str)

    def test_rejects_float_bool_negative_overflow_and_noncanonical_json(self):
        for value in (1.0, True, "1"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    Nanodollars(value)  # type: ignore[arg-type]
        for value in (-1, MAX_NANODOLLARS + 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Nanodollars(value)
        for value in (1, 1.0, True, None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    Nanodollars.from_json(value)
        for value in ("", "-1", "+1", "01", "1.0", " 1", "1e3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Nanodollars.from_json(value)

    def test_arithmetic_is_checked(self):
        self.assertEqual(Nanodollars(7), Nanodollars(3) + Nanodollars(4))
        self.assertEqual(Nanodollars(7), Nanodollars(10) - Nanodollars(3))
        self.assertEqual(
            Nanodollars(6), checked_sum((Nanodollars(1), Nanodollars(2), Nanodollars(3)))
        )
        with self.assertRaises(ValueError):
            _ = Nanodollars(MAX_NANODOLLARS) + Nanodollars(1)
        with self.assertRaises(ValueError):
            _ = Nanodollars(0) - Nanodollars(1)
        with self.assertRaises(TypeError):
            checked_sum((Nanodollars(1), 2))  # type: ignore[arg-type]


class IdentifierTests(unittest.TestCase):
    def test_identifiers_are_typed_immutable_and_portable(self):
        request = RequestId.from_json("request-1")
        self.assertEqual("request-1", request.to_json())
        self.assertNotEqual(request, OptionId("request-1"))
        with self.assertRaises(FrozenInstanceError):
            request.value = "changed"  # type: ignore[misc]

    def test_rejects_invalid_identifiers(self):
        for value in ("", "1starts-with-digit", "has space", "slash/value", "é", "a" * 129):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RequestId(value)
        with self.assertRaises(TypeError):
            RequestId.from_json(1)


class DecisionContractTests(unittest.TestCase):
    def test_selected_decision_records_all_candidates_and_versions(self):
        selected = candidate()
        blocked = candidate("strong-v1", eligible=False)
        decision = DecisionRecord(
            decision_id=DecisionId("decision-1"),
            request_id=RequestId("request-1"),
            workload_id=WorkloadId("workload-1"),
            policy_version=PolicyVersion("policy-v1"),
            snapshot_version=SnapshotVersion("snapshot-v1"),
            candidates=(selected, blocked),
            selected_option_id=selected.option_id,
            selection_probability=Probability.from_json("1"),
            randomization_seed="seed-1",
        )
        wire = decision.to_json()
        self.assertEqual("cheap-v1", wire["selectedOptionId"])
        self.assertEqual("1", wire["selectionProbability"])
        self.assertEqual(2, len(wire["candidates"]))
        self.assertEqual("10", wire["candidates"][0]["expectedCost"]["amountNanos"])
        json.dumps(wire)
        self.assertEqual(decision, DecisionRecord.from_json(wire))

    def test_unknown_estimate_is_explicit_and_never_zero(self):
        estimate = CostEstimate(EstimateState.UNKNOWN, "estimator-v1")
        self.assertEqual(
            {"state": "unknown", "estimatorVersion": "estimator-v1", "amountNanos": None},
            estimate.to_json(),
        )
        with self.assertRaises(ValueError):
            CostEstimate(EstimateState.UNKNOWN, "estimator-v1", Nanodollars(0))
        with self.assertRaises(ValueError):
            CostEstimate(EstimateState.KNOWN, "estimator-v1")

    def test_score_and_probability_reject_float_or_nonfinite_values(self):
        with self.assertRaises(TypeError):
            Score(0.5, "utility", "cal-v1")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            Score(Decimal("NaN"), "utility", "cal-v1")
        with self.assertRaises(TypeError):
            Probability(0.5)  # type: ignore[arg-type]
        for value in (Decimal("-0.1"), Decimal("1.1"), Decimal("Infinity")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Probability(value)
        for value in ("01", ".5", "1.1", "1e-1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Probability.from_json(value)

    def test_selection_must_be_present_and_eligible(self):
        common = dict(
            decision_id=DecisionId("decision-1"),
            request_id=RequestId("request-1"),
            workload_id=WorkloadId("workload-1"),
            policy_version=PolicyVersion("policy-v1"),
            snapshot_version=SnapshotVersion("snapshot-v1"),
            selection_probability=Probability(Decimal(1)),
            randomization_seed="seed-1",
        )
        with self.assertRaises(ValueError):
            DecisionRecord(
                **common,
                candidates=(candidate(),),
                selected_option_id=OptionId("missing-v1"),
            )
        blocked = candidate(eligible=False)
        with self.assertRaises(ValueError):
            DecisionRecord(
                **common,
                candidates=(blocked,),
                selected_option_id=blocked.option_id,
            )

    def test_deferral_requires_reason(self):
        common = dict(
            decision_id=DecisionId("decision-1"),
            request_id=RequestId("request-1"),
            workload_id=WorkloadId("workload-1"),
            policy_version=PolicyVersion("policy-v1"),
            snapshot_version=SnapshotVersion("snapshot-v1"),
            candidates=(candidate(eligible=False),),
            selected_option_id=None,
            selection_probability=Probability(Decimal(1)),
            randomization_seed="seed-1",
        )
        with self.assertRaises(TypeError):
            DecisionRecord(**common)
        self.assertEqual(
            "no_admissible_option",
            DecisionRecord(**common, deferral_reason="no_admissible_option").deferral_reason,
        )


class EventContractTests(unittest.TestCase):
    def test_trace_attempt_requires_authorization_identity(self):
        common = dict(
            event_id=EventId("event-1"),
            request_id=RequestId("request-1"),
            decision_id=DecisionId("decision-1"),
            option_id=OptionId("cheap-v1"),
            sequence=0,
            kind=TraceEventKind.ATTEMPT_STARTED,
            occurred_at="2026-09-15T12:00:00Z",
            detail_code="provider_dispatch",
        )
        with self.assertRaises(ValueError):
            TraceEvent(**common, attempt_id=AttemptId("attempt-1"))
        event = TraceEvent(
            **common,
            attempt_id=AttemptId("attempt-1"),
            authorization_id=AuthorizationId("authorization-1"),
        )
        self.assertEqual("attempt-1", event.to_json()["attemptId"])
        json.dumps(event.to_json())
        self.assertEqual(event, TraceEvent.from_json(event.to_json()))

    def test_usage_unknown_is_not_zero(self):
        common = dict(
            event_id=EventId("usage-1"),
            request_id=RequestId("request-1"),
            attempt_id=AttemptId("attempt-1"),
            authorization_id=AuthorizationId("authorization-1"),
            reservation_id=ReservationId("reservation-1"),
            occurred_at="2026-09-15T12:00:00Z",
            idempotency_key="provider-attempt-1",
        )
        unknown = UsageEvent(**common, state=UsageState.UNKNOWN)
        self.assertIsNone(unknown.to_json()["amountNanos"])
        self.assertEqual(unknown, UsageEvent.from_json(unknown.to_json()))
        with self.assertRaises(ValueError):
            UsageEvent(**common, state=UsageState.UNKNOWN, amount=Nanodollars(0))
        with self.assertRaises(ValueError):
            UsageEvent(**common, state=UsageState.KNOWN)

    def test_timestamps_must_be_canonical_utc(self):
        common = dict(
            event_id=EventId("event-1"),
            request_id=RequestId("request-1"),
            decision_id=DecisionId("decision-1"),
            option_id=OptionId("cheap-v1"),
            sequence=0,
            kind=TraceEventKind.OPTION_STARTED,
            detail_code="start",
        )
        for value in ("2026-09-15T12:00:00+00:00", "2026-09-15", "not-a-time"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    TraceEvent(**common, occurred_at=value)


class FeedbackContractTests(unittest.TestCase):
    def test_feedback_channels_remain_independent(self):
        event = FeedbackEvent(
            event_id=EventId("feedback-1"),
            request_id=RequestId("request-1"),
            output_id=OutputId("output-1"),
            user_vote=UserVote.MISSING,
            objective_result=ObjectiveResult.PASS,
            checker_result=CheckerResult.UNKNOWN,
            provenance="blind-evaluation-set-v1",
            evaluator_version=EvaluatorVersion("evaluator-v1"),
            observed_at="2026-09-15T12:00:00Z",
            visible_at="2026-09-15T12:01:00Z",
        )
        wire = event.to_json()
        self.assertEqual("missing", wire["userVote"])
        self.assertEqual("pass", wire["objectiveResult"])
        self.assertEqual("unknown", wire["checkerResult"])
        json.dumps(wire)
        self.assertEqual(event, FeedbackEvent.from_json(wire))

    def test_portable_records_reject_unknown_fields(self):
        event = FeedbackEvent(
            event_id=EventId("feedback-1"),
            request_id=RequestId("request-1"),
            output_id=OutputId("output-1"),
            user_vote=UserVote.ACCEPT,
            objective_result=ObjectiveResult.UNKNOWN,
            checker_result=CheckerResult.NOT_RUN,
            provenance="user-session-v1",
            evaluator_version=EvaluatorVersion("evaluator-v1"),
            observed_at="2026-09-15T12:00:00Z",
            visible_at="2026-09-15T12:00:00Z",
        )
        wire = event.to_json() | {"unexpected": True}
        with self.assertRaises(ValueError):
            FeedbackEvent.from_json(wire)

    def test_visibility_cannot_precede_observation(self):
        with self.assertRaises(ValueError):
            FeedbackEvent(
                event_id=EventId("feedback-1"),
                request_id=RequestId("request-1"),
                output_id=OutputId("output-1"),
                user_vote=UserVote.ABSTAIN,
                objective_result=ObjectiveResult.UNKNOWN,
                checker_result=CheckerResult.NOT_RUN,
                provenance="user-session-v1",
                evaluator_version=EvaluatorVersion("evaluator-v1"),
                observed_at="2026-09-15T12:01:00Z",
                visible_at="2026-09-15T12:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
