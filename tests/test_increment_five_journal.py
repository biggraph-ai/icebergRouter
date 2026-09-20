from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import EventId  # noqa: E402
from iceberg_router.core import (  # noqa: E402
    GENESIS_HASH,
    JournalConflict,
    JournalEventType,
    JournalIntegrityError,
    JournalRecord,
    SQLiteAuditJournal,
)


NOW = "2026-01-02T03:04:05Z"


def record(number: int, **changes) -> JournalRecord:
    values = {
        "event_id": EventId(f"event-{number}"),
        "event_type": JournalEventType.AUTHORIZATION,
        "occurred_at": NOW,
        "subject_id": f"request-{number}",
        "payload": {"amountNanos": str(number), "authorized": True},
        "idempotency_key": f"authorize:{number}",
    }
    values.update(changes)
    return JournalRecord(**values)


class JournalTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "journal.sqlite3"
        self.journal = SQLiteAuditJournal(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_append_creates_canonical_genesis_entry(self):
        result = self.journal.append(record(1))
        entry = result.entries[0]
        self.assertFalse(result.idempotent_replay)
        self.assertEqual(entry.sequence, 1)
        self.assertEqual(entry.previous_hash, GENESIS_HASH)
        self.assertEqual(entry.payload_json, '{"amountNanos":"1","authorized":true}')
        self.assertEqual(self.journal.verify_chain(), 1)

    def test_exact_replay_is_idempotent(self):
        first = self.journal.append(record(1))
        replay = self.journal.append(record(1))
        self.assertTrue(replay.idempotent_replay)
        self.assertEqual(first.entries, replay.entries)
        self.assertEqual(len(self.journal.entries()), 1)

    def test_identity_reuse_with_changed_content_is_rejected(self):
        self.journal.append(record(1))
        with self.assertRaises(JournalConflict):
            self.journal.append(record(1, payload={"amountNanos": "2"}))
        with self.assertRaises(JournalConflict):
            self.journal.append(record(2, idempotency_key="authorize:1"))

    def test_batch_is_atomic_and_partial_replay_is_rejected(self):
        self.journal.append_batch((record(1), record(2)))
        replay = self.journal.append_batch((record(1), record(2)))
        self.assertTrue(replay.idempotent_replay)
        with self.assertRaises(JournalConflict):
            self.journal.append_batch((record(2), record(3)))
        self.assertEqual(len(self.journal.entries()), 2)

    def test_correction_links_without_replacing_original(self):
        original = self.journal.append(record(1)).entries[0]
        result = self.journal.append_correction(
            EventId("event-correction"), original.event_id, NOW, "request-1",
            {"reason": "receipt-reconciled", "amountNanos": "2"}, "correct:1"
        )
        self.assertEqual(result.entries[0].correction_of_event_id, original.event_id)
        self.assertEqual(self.journal.entries()[0], original)
        self.assertEqual(self.journal.verify_chain(), 2)

    def test_correction_requires_existing_target(self):
        with self.assertRaises(JournalConflict):
            self.journal.append_correction(
                EventId("correction-1"), EventId("missing-event"), NOW,
                "request-1", {"reason": "test"}, "correct:missing"
            )

    def test_database_triggers_reject_update_and_delete(self):
        self.journal.append(record(1))
        connection = sqlite3.connect(self.path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE journal_entries SET subject_id = 'changed'")
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM journal_entries")
        finally:
            connection.close()

    def test_restart_preserves_and_verifies_chain(self):
        self.journal.append_batch((record(1), record(2)))
        reopened = SQLiteAuditJournal(self.path)
        self.assertEqual(reopened.verify_chain(), 2)
        self.assertEqual([entry.sequence for entry in reopened.entries()], [1, 2])

    def test_concurrent_writers_produce_one_contiguous_chain(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda number: self.journal.append(record(number)), range(1, 25)))
        entries = self.journal.entries()
        self.assertEqual([entry.sequence for entry in entries], list(range(1, 25)))
        self.assertEqual(self.journal.verify_chain(), 24)

    def test_nonportable_payload_is_rejected(self):
        with self.assertRaises(TypeError):
            record(1, payload={"estimatedCost": 1.25})
        with self.assertRaises(ValueError):
            record(1, payload={"large": 2**63})

    def test_tampering_is_detected_even_if_guard_is_removed(self):
        self.journal.append_batch((record(1), record(2)))
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("DROP TRIGGER journal_no_update")
            connection.execute(
                "UPDATE journal_entries SET payload_json = ? WHERE sequence = 1",
                ('{"amountNanos":"999","authorized":true}',),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(JournalIntegrityError):
            self.journal.verify_chain()

    def test_empty_and_duplicate_batches_are_rejected(self):
        with self.assertRaises(ValueError):
            self.journal.append_batch(())
        with self.assertRaises(ValueError):
            self.journal.append_batch((record(1), record(1)))


if __name__ == "__main__":
    unittest.main()
