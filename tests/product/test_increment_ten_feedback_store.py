from pathlib import Path
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    CheckerResult,
    EvaluatorVersion,
    EventId,
    FeedbackEvent,
    ObjectiveResult,
    OutputId,
    RequestId,
    UserVote,
)
from iceberg_router.core import (  # noqa: E402
    FeedbackStoreError,
    JournalEventType,
    JournalFeedbackStore,
    JournalRecord,
    SQLiteAuditJournal,
)


def feedback(
    number: int,
    *,
    request: str = "request-1",
    output: str = "output-1",
    observed: str = "2026-09-16T10:00:00Z",
    visible: str = "2026-09-16T11:00:00Z",
    vote: UserVote = UserVote.MISSING,
    objective: ObjectiveResult = ObjectiveResult.UNKNOWN,
    checker: CheckerResult = CheckerResult.NOT_RUN,
) -> FeedbackEvent:
    return FeedbackEvent(
        EventId(f"feedback-{number}"),
        RequestId(request),
        OutputId(output),
        vote,
        objective,
        checker,
        "offline-fixture",
        EvaluatorVersion("evaluator-v1"),
        observed,
        visible,
    )


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "journal.sqlite3"
        self.journal = SQLiteAuditJournal(self.path)
        self.store = JournalFeedbackStore(self.journal)

    def tearDown(self):
        self.temporary.cleanup()

    def test_snapshot_excludes_feedback_until_visibility_time(self):
        event = feedback(1)
        self.store.append(event)
        before = self.store.snapshot("2026-09-16T10:30:00Z")
        at_visibility = self.store.snapshot("2026-09-16T11:00:00Z")
        self.assertEqual(before.events, ())
        self.assertEqual(at_visibility.events, (event,))

    def test_missing_and_disagreeing_feedback_channels_are_preserved(self):
        missing = feedback(1)
        disagreement = feedback(
            2,
            vote=UserVote.ACCEPT,
            objective=ObjectiveResult.FAIL,
            checker=CheckerResult.PASS,
        )
        self.store.append(missing)
        self.store.append(disagreement)
        snapshot = self.store.snapshot("2026-09-16T12:00:00Z")
        self.assertEqual(snapshot.events[0].user_vote, UserVote.MISSING)
        self.assertEqual(snapshot.events[1].user_vote, UserVote.ACCEPT)
        self.assertEqual(snapshot.events[1].objective_result, ObjectiveResult.FAIL)
        self.assertEqual(snapshot.events[1].checker_result, CheckerResult.PASS)

    def test_append_is_idempotent_without_rewriting_history(self):
        event = feedback(1)
        first = self.store.append(event)
        replay = self.store.append(event)
        self.assertFalse(first.idempotent_replay)
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(len(self.journal.entries()), 1)

    def test_snapshot_filters_request_and_output(self):
        wanted = feedback(1)
        self.store.append(wanted)
        self.store.append(feedback(2, request="request-2"))
        self.store.append(feedback(3, output="output-2"))
        by_request = self.store.snapshot(
            "2026-09-16T12:00:00Z", request_id=RequestId("request-1")
        )
        by_output = self.store.snapshot(
            "2026-09-16T12:00:00Z", output_id=OutputId("output-1")
        )
        self.assertEqual([item.event_id.value for item in by_request.events], [
            "feedback-1", "feedback-3"
        ])
        self.assertEqual([item.event_id.value for item in by_output.events], [
            "feedback-1", "feedback-2"
        ])

    def test_snapshot_version_is_deterministic_across_restart(self):
        self.store.append(feedback(1))
        first = self.store.snapshot("2026-09-16T12:00:00Z")
        reopened = JournalFeedbackStore(SQLiteAuditJournal(self.path))
        second = reopened.snapshot("2026-09-16T12:00:00Z")
        self.assertEqual(first, second)
        self.store.append(feedback(2))
        historical = self.store.snapshot(
            "2026-09-16T12:00:00Z",
            journal_through_sequence=first.journal_through_sequence,
        )
        current = self.store.snapshot("2026-09-16T12:00:00Z")
        self.assertEqual(historical, first)
        self.assertNotEqual(current.snapshot_version, first.snapshot_version)

    def test_snapshot_orders_by_visibility_not_append_order(self):
        later = feedback(1, visible="2026-09-16T12:00:00Z")
        earlier = feedback(
            2,
            observed="2026-09-16T09:00:00Z",
            visible="2026-09-16T10:00:00Z",
        )
        self.store.append(later)
        self.store.append(earlier)
        snapshot = self.store.snapshot("2026-09-16T13:00:00Z")
        self.assertEqual(snapshot.events, (earlier, later))

    def test_non_feedback_entries_are_ignored_but_malformed_feedback_fails(self):
        self.journal.append(
            JournalRecord(
                EventId("decision-event"),
                JournalEventType.DECISION,
                "2026-09-16T09:00:00Z",
                "decision-1",
                {"kind": "test"},
                "decision:1",
            )
        )
        self.assertEqual(
            self.store.snapshot("2026-09-16T12:00:00Z").events, ()
        )
        self.journal.append(
            JournalRecord(
                EventId("bad-feedback"),
                JournalEventType.FEEDBACK,
                "2026-09-16T10:00:00Z",
                "request-1",
                {"not": "a feedback event"},
                "feedback:bad",
            )
        )
        with self.assertRaises(FeedbackStoreError):
            self.store.snapshot("2026-09-16T12:00:00Z")

    def test_filter_and_cutoff_types_are_strict(self):
        with self.assertRaises(ValueError):
            self.store.snapshot("2026-09-16T12:00:00+00:00")
        with self.assertRaises(TypeError):
            self.store.snapshot("2026-09-16T12:00:00Z", request_id="request-1")
        with self.assertRaises(ValueError):
            self.store.snapshot("2026-09-16T12:00:00Z", journal_through_sequence=1)
        with self.assertRaises(TypeError):
            JournalFeedbackStore(object())


if __name__ == "__main__":
    unittest.main()
