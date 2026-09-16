"""Durable append-only audit journal with a verifiable hash chain.

The journal records facts; it is deliberately not the budget authority.  Ledger
state remains authoritative for admission and settlement.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Sequence

from iceberg_router.contracts._validation import require_text, require_utc_timestamp
from iceberg_router.contracts.decisions import DecisionRecord
from iceberg_router.contracts.events import TraceEvent, UsageEvent
from iceberg_router.contracts.feedback import FeedbackEvent
from iceberg_router.contracts.identifiers import EventId

from .executor import ExecutionRequest, ExecutionResult


GENESIS_HASH = "0" * 64


class JournalError(RuntimeError):
    """Base journal failure."""


class JournalConflict(JournalError):
    """An identity or idempotency key was reused for different content."""


class JournalIntegrityError(JournalError):
    """The stored sequence or hash chain failed verification."""


class JournalEventType(str, Enum):
    DECISION = "decision"
    TRACE = "trace"
    USAGE = "usage"
    FEEDBACK = "feedback"
    AUTHORIZATION = "authorization"
    SETTLEMENT = "settlement"
    EXECUTION = "execution"
    CORRECTION = "correction"


@dataclass(frozen=True, slots=True)
class JournalRecord:
    event_id: EventId
    event_type: JournalEventType
    occurred_at: str
    subject_id: str
    payload: object
    idempotency_key: str
    correction_of_event_id: EventId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, EventId):
            raise TypeError("event_id must be EventId")
        if not isinstance(self.event_type, JournalEventType):
            raise TypeError("event_type must be JournalEventType")
        require_utc_timestamp(self.occurred_at, "occurred_at")
        require_text(self.subject_id, "subject_id", maximum=256)
        require_text(self.idempotency_key, "idempotency_key", maximum=256)
        _canonical_payload(self.payload)
        if self.correction_of_event_id is not None and not isinstance(
            self.correction_of_event_id, EventId
        ):
            raise TypeError("correction_of_event_id must be EventId or None")
        if (self.event_type is JournalEventType.CORRECTION) != (
            self.correction_of_event_id is not None
        ):
            raise ValueError("correction records must identify an existing event")


@dataclass(frozen=True, slots=True)
class JournalEntry:
    sequence: int
    event_id: EventId
    event_type: JournalEventType
    occurred_at: str
    subject_id: str
    payload_json: str
    previous_hash: str
    entry_hash: str
    idempotency_key: str
    correction_of_event_id: EventId | None

    @property
    def payload(self) -> object:
        return json.loads(self.payload_json)


@dataclass(frozen=True, slots=True)
class JournalAppendResult:
    entries: tuple[JournalEntry, ...]
    idempotent_replay: bool


def _validate_json(value: object, path: str = "payload") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if not -(2**63) <= value <= 2**63 - 1:
            raise ValueError(f"{path} integer is outside the portable signed 64-bit range")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for key, item in value.items():
            _validate_json(item, f"{path}.{key}")
        return
    raise TypeError(f"{path} must contain only portable JSON values (floats are forbidden)")


def _canonical_payload(payload: object) -> str:
    _validate_json(payload)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_material(
    sequence: int, record: JournalRecord, payload_json: str, previous_hash: str
) -> str:
    material = {
        "correctionOfEventId": (
            None
            if record.correction_of_event_id is None
            else record.correction_of_event_id.value
        ),
        "eventId": record.event_id.value,
        "eventType": record.event_type.value,
        "occurredAt": record.occurred_at,
        "payload": json.loads(payload_json),
        "previousHash": previous_hash,
        "sequence": sequence,
        "subjectId": record.subject_id,
    }
    encoded = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SQLiteAuditJournal:
    """A process-safe SQLite journal whose rows cannot be updated or deleted."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    sequence INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL UNIQUE,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    correction_of_event_id TEXT NULL
                );
                CREATE TRIGGER IF NOT EXISTS journal_no_update
                BEFORE UPDATE ON journal_entries BEGIN
                    SELECT RAISE(ABORT, 'journal entries are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS journal_no_delete
                BEFORE DELETE ON journal_entries BEGIN
                    SELECT RAISE(ABORT, 'journal entries are immutable');
                END;
                """
            )
        finally:
            connection.close()

    def append(self, record: JournalRecord) -> JournalAppendResult:
        return self.append_batch((record,))

    def append_batch(self, records: Sequence[JournalRecord]) -> JournalAppendResult:
        if not records:
            raise ValueError("records must not be empty")
        if any(not isinstance(record, JournalRecord) for record in records):
            raise TypeError("records must contain JournalRecord values")
        if len({record.event_id for record in records}) != len(records):
            raise ValueError("batch event IDs must be unique")
        if len({record.idempotency_key for record in records}) != len(records):
            raise ValueError("batch idempotency keys must be unique")
        with self._transaction() as connection:
            existing = [self._find_existing(connection, record) for record in records]
            if all(item is not None for item in existing):
                return JournalAppendResult(tuple(existing), True)  # type: ignore[arg-type]
            if any(item is not None for item in existing):
                raise JournalConflict("batch is a partial replay")
            tail = connection.execute(
                "SELECT sequence, entry_hash FROM journal_entries ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            sequence = 1 if tail is None else tail["sequence"] + 1
            previous_hash = GENESIS_HASH if tail is None else tail["entry_hash"]
            appended: list[JournalEntry] = []
            for record in records:
                if record.correction_of_event_id is not None:
                    target = connection.execute(
                        "SELECT 1 FROM journal_entries WHERE event_id = ?",
                        (record.correction_of_event_id.value,),
                    ).fetchone()
                    if target is None:
                        raise JournalConflict("correction target does not exist")
                payload_json = _canonical_payload(record.payload)
                entry_hash = _hash_material(sequence, record, payload_json, previous_hash)
                try:
                    connection.execute(
                        """INSERT INTO journal_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sequence,
                            record.event_id.value,
                            record.event_type.value,
                            record.occurred_at,
                            record.subject_id,
                            payload_json,
                            previous_hash,
                            entry_hash,
                            record.idempotency_key,
                            None if record.correction_of_event_id is None else record.correction_of_event_id.value,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise JournalConflict("journal identity already exists") from error
                entry = self._entry_from_values(sequence, record, payload_json, previous_hash, entry_hash)
                appended.append(entry)
                sequence += 1
                previous_hash = entry_hash
            return JournalAppendResult(tuple(appended), False)

    def _find_existing(
        self, connection: sqlite3.Connection, record: JournalRecord
    ) -> JournalEntry | None:
        rows = connection.execute(
            "SELECT * FROM journal_entries WHERE event_id = ? OR idempotency_key = ?",
            (record.event_id.value, record.idempotency_key),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise JournalConflict("event ID and idempotency key identify different entries")
        entry = self._row_to_entry(rows[0])
        payload = _canonical_payload(record.payload)
        if (
            entry.event_id != record.event_id
            or entry.event_type is not record.event_type
            or entry.occurred_at != record.occurred_at
            or entry.subject_id != record.subject_id
            or entry.payload_json != payload
            or entry.correction_of_event_id != record.correction_of_event_id
            or entry.idempotency_key != record.idempotency_key
        ):
            raise JournalConflict("journal identity was reused for different content")
        return entry

    @staticmethod
    def _entry_from_values(
        sequence: int,
        record: JournalRecord,
        payload_json: str,
        previous_hash: str,
        entry_hash: str,
    ) -> JournalEntry:
        return JournalEntry(sequence, record.event_id, record.event_type, record.occurred_at,
            record.subject_id, payload_json, previous_hash, entry_hash,
            record.idempotency_key, record.correction_of_event_id)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> JournalEntry:
        correction = row["correction_of_event_id"]
        try:
            event_type = JournalEventType(row["event_type"])
        except ValueError as error:
            raise JournalIntegrityError("stored event type is invalid") from error
        return JournalEntry(
            row["sequence"], EventId(row["event_id"]), event_type, row["occurred_at"],
            row["subject_id"], row["payload_json"], row["previous_hash"],
            row["entry_hash"], row["idempotency_key"],
            None if correction is None else EventId(correction),
        )

    def entries(self) -> tuple[JournalEntry, ...]:
        connection = self._connect()
        try:
            rows = connection.execute("SELECT * FROM journal_entries ORDER BY sequence").fetchall()
            return tuple(self._row_to_entry(row) for row in rows)
        finally:
            connection.close()

    def verify_chain(self) -> int:
        previous_hash = GENESIS_HASH
        entries = self.entries()
        for expected, entry in enumerate(entries, start=1):
            record = JournalRecord(entry.event_id, entry.event_type, entry.occurred_at,
                entry.subject_id, entry.payload, entry.idempotency_key,
                entry.correction_of_event_id)
            expected_hash = _hash_material(expected, record, entry.payload_json, previous_hash)
            if (entry.sequence != expected or entry.previous_hash != previous_hash
                    or entry.entry_hash != expected_hash):
                raise JournalIntegrityError(f"journal chain is invalid at sequence {expected}")
            previous_hash = entry.entry_hash
        return len(entries)

    def append_decision(self, event_id: EventId, occurred_at: str,
                        decision: DecisionRecord, idempotency_key: str) -> JournalAppendResult:
        return self.append(JournalRecord(event_id, JournalEventType.DECISION, occurred_at,
            decision.decision_id.value, decision.to_json(), idempotency_key))

    def append_trace(self, event: TraceEvent) -> JournalAppendResult:
        return self.append(JournalRecord(event.event_id, JournalEventType.TRACE,
            event.occurred_at, event.request_id.value, event.to_json(),
            f"trace:{event.event_id.value}"))

    def append_usage(self, event: UsageEvent) -> JournalAppendResult:
        return self.append(JournalRecord(event.event_id, JournalEventType.USAGE,
            event.occurred_at, event.request_id.value, event.to_json(), event.idempotency_key))

    def append_feedback(self, event: FeedbackEvent) -> JournalAppendResult:
        return self.append(JournalRecord(event.event_id, JournalEventType.FEEDBACK,
            event.visible_at, event.request_id.value, event.to_json(),
            f"feedback:{event.event_id.value}"))

    def record_execution(self, event_id: EventId, occurred_at: str,
                         request: ExecutionRequest, result: ExecutionResult,
                         idempotency_key: str) -> JournalAppendResult:
        traces = tuple(JournalRecord(event.event_id, JournalEventType.TRACE,
            event.occurred_at, event.request_id.value, event.to_json(),
            f"trace:{event.event_id.value}") for event in result.trace)
        summary: dict[str, Any] = {
            "attemptIds": [attempt.attempt_id.value for attempt in result.attempts],
            "decisionId": request.decision_id.value,
            "outputReference": result.output_reference,
            "requestId": request.request_id.value,
            "resultCode": result.result_code,
            "status": result.status.value,
            "terminalNodeId": None if result.terminal_node_id is None else result.terminal_node_id.value,
        }
        return self.append_batch((*traces, JournalRecord(event_id,
            JournalEventType.EXECUTION, occurred_at, request.request_id.value,
            summary, idempotency_key)))

    def append_correction(self, event_id: EventId, correction_of_event_id: EventId,
                          occurred_at: str, subject_id: str, payload: object,
                          idempotency_key: str) -> JournalAppendResult:
        return self.append(JournalRecord(event_id, JournalEventType.CORRECTION,
            occurred_at, subject_id, payload, idempotency_key,
            correction_of_event_id))
