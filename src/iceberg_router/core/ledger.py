"""Durable single-host budget accounting backed by SQLite."""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Iterator

from iceberg_router.contracts.identifiers import (
    AccountId,
    AttemptId,
    AuthorizationId,
    BudgetId,
    DecisionId,
    RequestId,
    ReservationId,
)
from iceberg_router.contracts.money import Nanodollars


class LedgerError(RuntimeError):
    """Base class for accounting failures."""


class DuplicateConflict(LedgerError):
    """An identifier or idempotency key was reused with different data."""


class BudgetNotFound(LedgerError):
    """The requested budget does not exist."""


class AdmissionDenied(LedgerError):
    """The requested liability cannot be admitted."""


class InvalidTransition(LedgerError):
    """The requested state transition is not legal."""


class BudgetContractBreach(LedgerError):
    """Actual cost exceeded the authorization bound; the budget is halted."""


class ReservationState(str, Enum):
    HELD = "held"
    PENDING = "pending"
    SETTLED = "settled"
    BREACHED = "breached"


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    budget_id: BudgetId
    total: Nanodollars
    confirmed_spend: Nanodollars
    outstanding_liability: Nanodollars
    available: Nanodollars
    halted: bool


@dataclass(frozen=True, slots=True)
class ReservationRecord:
    reservation_id: ReservationId
    budget_id: BudgetId
    request_id: RequestId
    decision_id: DecisionId
    account_id: AccountId
    max_liability: Nanodollars
    state: ReservationState
    actual_cost: Nanodollars | None
    settlement_key: str | None


@dataclass(frozen=True, slots=True)
class AuthorizationRecord:
    authorization_id: AuthorizationId
    reservation_id: ReservationId
    attempt_id: AttemptId


@dataclass(frozen=True, slots=True)
class SettlementResult:
    reservation: ReservationRecord
    idempotent_replay: bool


_SCHEMA = """
CREATE TABLE IF NOT EXISTS budgets (
    budget_id TEXT PRIMARY KEY,
    total_nanos INTEGER NOT NULL CHECK(total_nanos >= 0),
    halted INTEGER NOT NULL DEFAULT 0 CHECK(halted IN (0, 1))
);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL REFERENCES budgets(budget_id),
    request_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    max_liability_nanos INTEGER NOT NULL CHECK(max_liability_nanos >= 0),
    state TEXT NOT NULL CHECK(state IN ('held', 'pending', 'settled', 'breached')),
    actual_cost_nanos INTEGER CHECK(actual_cost_nanos >= 0),
    settlement_key TEXT,
    UNIQUE(budget_id, settlement_key)
);

CREATE TABLE IF NOT EXISTS authorizations (
    authorization_id TEXT PRIMARY KEY,
    reservation_id TEXT NOT NULL UNIQUE REFERENCES reservations(reservation_id),
    attempt_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ledger_updates (
    budget_id TEXT NOT NULL REFERENCES budgets(budget_id),
    idempotency_key TEXT NOT NULL,
    reservation_id TEXT NOT NULL REFERENCES reservations(reservation_id),
    update_kind TEXT NOT NULL CHECK(update_kind IN ('pending', 'settled', 'breached')),
    actual_cost_nanos INTEGER CHECK(actual_cost_nanos >= 0),
    PRIMARY KEY(budget_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS reservations_budget_state
    ON reservations(budget_id, state);
"""


class SQLiteBudgetLedger:
    """Transactional liability ledger for one SQLite database.

    Every mutation obtains a SQLite write lock with ``BEGIN IMMEDIATE``. A held or
    pending reservation contributes its full maximum liability. Settlement swaps
    that hold for an authoritative actual amount. The class creates no retries or
    authorizations implicitly.
    """

    def __init__(self, path: str | Path, *, timeout_seconds: float = 5.0):
        self.path = Path(path)
        if self.path == Path(":memory:"):
            raise ValueError("a durable filesystem path is required")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise TypeError("timeout_seconds must be numeric")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def create_budget(self, budget_id: BudgetId, total: Nanodollars) -> BudgetSnapshot:
        self._require_type(budget_id, BudgetId, "budget_id")
        self._require_type(total, Nanodollars, "total")
        with self._write() as connection:
            existing = connection.execute(
                "SELECT total_nanos FROM budgets WHERE budget_id = ?", (budget_id.value,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO budgets(budget_id, total_nanos) VALUES (?, ?)",
                    (budget_id.value, total.value),
                )
            elif existing["total_nanos"] != total.value:
                raise DuplicateConflict("budget ID already exists with a different total")
            return self._snapshot(connection, budget_id)

    def snapshot(self, budget_id: BudgetId) -> BudgetSnapshot:
        self._require_type(budget_id, BudgetId, "budget_id")
        with closing(self._connect()) as connection:
            return self._snapshot(connection, budget_id)

    def reserve(
        self,
        *,
        budget_id: BudgetId,
        reservation_id: ReservationId,
        request_id: RequestId,
        decision_id: DecisionId,
        account_id: AccountId,
        max_liability: Nanodollars,
    ) -> ReservationRecord:
        typed = (
            (budget_id, BudgetId, "budget_id"),
            (reservation_id, ReservationId, "reservation_id"),
            (request_id, RequestId, "request_id"),
            (decision_id, DecisionId, "decision_id"),
            (account_id, AccountId, "account_id"),
            (max_liability, Nanodollars, "max_liability"),
        )
        for value, expected, name in typed:
            self._require_type(value, expected, name)

        with self._write() as connection:
            existing = self._reservation_row(connection, reservation_id)
            if existing is not None:
                record = self._record(existing)
                expected_record = (
                    budget_id,
                    request_id,
                    decision_id,
                    account_id,
                    max_liability,
                )
                actual_record = (
                    record.budget_id,
                    record.request_id,
                    record.decision_id,
                    record.account_id,
                    record.max_liability,
                )
                if actual_record != expected_record:
                    raise DuplicateConflict(
                        "reservation ID already exists with different authorization inputs"
                    )
                return record

            snapshot = self._snapshot(connection, budget_id)
            if snapshot.halted:
                raise AdmissionDenied("budget is halted after a contract breach")
            if max_liability > snapshot.available:
                raise AdmissionDenied("upper liability exceeds available budget")
            connection.execute(
                """
                INSERT INTO reservations(
                    reservation_id, budget_id, request_id, decision_id, account_id,
                    max_liability_nanos, state
                ) VALUES (?, ?, ?, ?, ?, ?, 'held')
                """,
                (
                    reservation_id.value,
                    budget_id.value,
                    request_id.value,
                    decision_id.value,
                    account_id.value,
                    max_liability.value,
                ),
            )
            return self._record(self._reservation_row(connection, reservation_id))

    def authorize_attempt(
        self,
        *,
        reservation_id: ReservationId,
        authorization_id: AuthorizationId,
        attempt_id: AttemptId,
    ) -> AuthorizationRecord:
        for value, expected, name in (
            (reservation_id, ReservationId, "reservation_id"),
            (authorization_id, AuthorizationId, "authorization_id"),
            (attempt_id, AttemptId, "attempt_id"),
        ):
            self._require_type(value, expected, name)
        with self._write() as connection:
            reservation = self._reservation_row(connection, reservation_id)
            if reservation is None:
                raise InvalidTransition("reservation does not exist")
            existing = connection.execute(
                "SELECT * FROM authorizations WHERE authorization_id = ?",
                (authorization_id.value,),
            ).fetchone()
            if existing is not None:
                record = self._authorization_record(existing)
                if record != AuthorizationRecord(authorization_id, reservation_id, attempt_id):
                    raise DuplicateConflict(
                        "authorization ID already exists with a different attempt"
                    )
                return record
            if ReservationState(reservation["state"]) is not ReservationState.HELD:
                raise InvalidTransition("only a held reservation can authorize an attempt")
            try:
                connection.execute(
                    """
                    INSERT INTO authorizations(authorization_id, reservation_id, attempt_id)
                    VALUES (?, ?, ?)
                    """,
                    (authorization_id.value, reservation_id.value, attempt_id.value),
                )
            except sqlite3.IntegrityError as error:
                raise DuplicateConflict(
                    "reservation or attempt already has an authorization"
                ) from error
            row = connection.execute(
                "SELECT * FROM authorizations WHERE authorization_id = ?",
                (authorization_id.value,),
            ).fetchone()
            return self._authorization_record(row)

    def reserve_and_authorize(
        self,
        *,
        budget_id: BudgetId,
        reservation_id: ReservationId,
        request_id: RequestId,
        decision_id: DecisionId,
        account_id: AccountId,
        max_liability: Nanodollars,
        authorization_id: AuthorizationId,
        attempt_id: AttemptId,
    ) -> tuple[ReservationRecord, AuthorizationRecord]:
        """Atomically reserve liability and bind exactly one attempt.

        If either the admission check or attempt-identity insertion fails, neither
        record is created. Repeating the identical operation is idempotent.
        """

        for value, expected, name in (
            (budget_id, BudgetId, "budget_id"),
            (reservation_id, ReservationId, "reservation_id"),
            (request_id, RequestId, "request_id"),
            (decision_id, DecisionId, "decision_id"),
            (account_id, AccountId, "account_id"),
            (max_liability, Nanodollars, "max_liability"),
            (authorization_id, AuthorizationId, "authorization_id"),
            (attempt_id, AttemptId, "attempt_id"),
        ):
            self._require_type(value, expected, name)

        with self._write() as connection:
            reservation_row = self._reservation_row(connection, reservation_id)
            if reservation_row is None:
                snapshot = self._snapshot(connection, budget_id)
                if snapshot.halted:
                    raise AdmissionDenied("budget is halted after a contract breach")
                if max_liability > snapshot.available:
                    raise AdmissionDenied("upper liability exceeds available budget")
                connection.execute(
                    """
                    INSERT INTO reservations(
                        reservation_id, budget_id, request_id, decision_id, account_id,
                        max_liability_nanos, state
                    ) VALUES (?, ?, ?, ?, ?, ?, 'held')
                    """,
                    (
                        reservation_id.value,
                        budget_id.value,
                        request_id.value,
                        decision_id.value,
                        account_id.value,
                        max_liability.value,
                    ),
                )
                reservation_row = self._required_reservation_row(connection, reservation_id)
            else:
                record = self._record(reservation_row)
                if (
                    record.budget_id,
                    record.request_id,
                    record.decision_id,
                    record.account_id,
                    record.max_liability,
                ) != (budget_id, request_id, decision_id, account_id, max_liability):
                    raise DuplicateConflict(
                        "reservation ID already exists with different authorization inputs"
                    )

            existing = connection.execute(
                "SELECT * FROM authorizations WHERE authorization_id = ?",
                (authorization_id.value,),
            ).fetchone()
            expected_authorization = AuthorizationRecord(
                authorization_id, reservation_id, attempt_id
            )
            if existing is not None:
                authorization = self._authorization_record(existing)
                if authorization != expected_authorization:
                    raise DuplicateConflict(
                        "authorization ID already exists with a different attempt"
                    )
                return self._record(reservation_row), authorization
            if ReservationState(reservation_row["state"]) is not ReservationState.HELD:
                raise InvalidTransition("only a held reservation can authorize an attempt")
            try:
                connection.execute(
                    """
                    INSERT INTO authorizations(authorization_id, reservation_id, attempt_id)
                    VALUES (?, ?, ?)
                    """,
                    (authorization_id.value, reservation_id.value, attempt_id.value),
                )
            except sqlite3.IntegrityError as error:
                raise DuplicateConflict(
                    "reservation or attempt already has an authorization"
                ) from error
            authorization_row = connection.execute(
                "SELECT * FROM authorizations WHERE authorization_id = ?",
                (authorization_id.value,),
            ).fetchone()
            return self._record(reservation_row), self._authorization_record(authorization_row)

    def mark_pending(self, reservation_id: ReservationId, *, idempotency_key: str) -> SettlementResult:
        self._require_type(reservation_id, ReservationId, "reservation_id")
        self._require_key(idempotency_key)
        with self._write() as connection:
            row = self._required_reservation_row(connection, reservation_id)
            state = ReservationState(row["state"])
            if state is ReservationState.PENDING and row["settlement_key"] == idempotency_key:
                return SettlementResult(self._record(row), True)
            if state is not ReservationState.HELD:
                raise DuplicateConflict("reservation already has a different terminal update")
            self._require_authorized(connection, reservation_id)
            self._claim_update_key(
                connection,
                budget_id=BudgetId(row["budget_id"]),
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
                update_kind=ReservationState.PENDING,
                actual_cost=None,
            )
            connection.execute(
                """
                UPDATE reservations SET state = 'pending', settlement_key = ?
                WHERE reservation_id = ?
                """,
                (idempotency_key, reservation_id.value),
            )
            return SettlementResult(
                self._record(self._required_reservation_row(connection, reservation_id)), False
            )

    def settle(
        self,
        reservation_id: ReservationId,
        *,
        actual_cost: Nanodollars,
        idempotency_key: str,
    ) -> SettlementResult:
        self._require_type(reservation_id, ReservationId, "reservation_id")
        self._require_type(actual_cost, Nanodollars, "actual_cost")
        self._require_key(idempotency_key)
        breached = False
        with self._write() as connection:
            row = self._required_reservation_row(connection, reservation_id)
            state = ReservationState(row["state"])
            if state in (ReservationState.SETTLED, ReservationState.BREACHED):
                if (
                    row["settlement_key"] == idempotency_key
                    and row["actual_cost_nanos"] == actual_cost.value
                ):
                    return SettlementResult(self._record(row), True)
                raise DuplicateConflict("reservation already has a different settlement")
            self._require_authorized(connection, reservation_id)
            target_state = ReservationState.SETTLED
            if actual_cost.value > row["max_liability_nanos"]:
                target_state = ReservationState.BREACHED
                breached = True
            self._claim_update_key(
                connection,
                budget_id=BudgetId(row["budget_id"]),
                reservation_id=reservation_id,
                idempotency_key=idempotency_key,
                update_kind=target_state,
                actual_cost=actual_cost,
            )
            connection.execute(
                """
                UPDATE reservations
                SET state = ?, actual_cost_nanos = ?, settlement_key = ?
                WHERE reservation_id = ?
                """,
                (
                    target_state.value,
                    actual_cost.value,
                    idempotency_key,
                    reservation_id.value,
                ),
            )
            if breached:
                connection.execute(
                    "UPDATE budgets SET halted = 1 WHERE budget_id = ?",
                    (row["budget_id"],),
                )
            result = SettlementResult(
                self._record(self._required_reservation_row(connection, reservation_id)), False
            )
        if breached:
            raise BudgetContractBreach(
                "actual cost exceeded held liability; charge recorded and budget halted"
            )
        return result

    def get_reservation(self, reservation_id: ReservationId) -> ReservationRecord:
        self._require_type(reservation_id, ReservationId, "reservation_id")
        with closing(self._connect()) as connection:
            return self._record(self._required_reservation_row(connection, reservation_id))

    def _snapshot(self, connection: sqlite3.Connection, budget_id: BudgetId) -> BudgetSnapshot:
        budget = connection.execute(
            "SELECT * FROM budgets WHERE budget_id = ?", (budget_id.value,)
        ).fetchone()
        if budget is None:
            raise BudgetNotFound(f"budget {budget_id.value!r} does not exist")
        rows = connection.execute(
            "SELECT state, max_liability_nanos, actual_cost_nanos FROM reservations WHERE budget_id = ?",
            (budget_id.value,),
        ).fetchall()
        confirmed_value = sum(
            row["actual_cost_nanos"]
            for row in rows
            if row["state"] in (ReservationState.SETTLED.value, ReservationState.BREACHED.value)
        )
        outstanding_value = sum(
            row["max_liability_nanos"]
            for row in rows
            if row["state"] in (ReservationState.HELD.value, ReservationState.PENDING.value)
        )
        total_value = budget["total_nanos"]
        used = confirmed_value + outstanding_value
        available_value = max(0, total_value - used)
        return BudgetSnapshot(
            budget_id=budget_id,
            total=Nanodollars(total_value),
            confirmed_spend=Nanodollars(confirmed_value),
            outstanding_liability=Nanodollars(outstanding_value),
            available=Nanodollars(available_value),
            halted=bool(budget["halted"]),
        )

    @staticmethod
    def _reservation_row(
        connection: sqlite3.Connection, reservation_id: ReservationId
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id.value,)
        ).fetchone()

    def _required_reservation_row(
        self, connection: sqlite3.Connection, reservation_id: ReservationId
    ) -> sqlite3.Row:
        row = self._reservation_row(connection, reservation_id)
        if row is None:
            raise InvalidTransition("reservation does not exist")
        return row

    @staticmethod
    def _require_authorized(
        connection: sqlite3.Connection, reservation_id: ReservationId
    ) -> None:
        row = connection.execute(
            "SELECT 1 FROM authorizations WHERE reservation_id = ?", (reservation_id.value,)
        ).fetchone()
        if row is None:
            raise InvalidTransition("reservation has no authorized attempt")

    @staticmethod
    def _record(row: sqlite3.Row | None) -> ReservationRecord:
        if row is None:
            raise RuntimeError("expected reservation row")
        actual = row["actual_cost_nanos"]
        return ReservationRecord(
            reservation_id=ReservationId(row["reservation_id"]),
            budget_id=BudgetId(row["budget_id"]),
            request_id=RequestId(row["request_id"]),
            decision_id=DecisionId(row["decision_id"]),
            account_id=AccountId(row["account_id"]),
            max_liability=Nanodollars(row["max_liability_nanos"]),
            state=ReservationState(row["state"]),
            actual_cost=None if actual is None else Nanodollars(actual),
            settlement_key=row["settlement_key"],
        )

    @staticmethod
    def _authorization_record(row: sqlite3.Row | None) -> AuthorizationRecord:
        if row is None:
            raise RuntimeError("expected authorization row")
        return AuthorizationRecord(
            AuthorizationId(row["authorization_id"]),
            ReservationId(row["reservation_id"]),
            AttemptId(row["attempt_id"]),
        )

    @staticmethod
    def _claim_update_key(
        connection: sqlite3.Connection,
        *,
        budget_id: BudgetId,
        reservation_id: ReservationId,
        idempotency_key: str,
        update_kind: ReservationState,
        actual_cost: Nanodollars | None,
    ) -> None:
        try:
            connection.execute(
                """
                INSERT INTO ledger_updates(
                    budget_id, idempotency_key, reservation_id, update_kind,
                    actual_cost_nanos
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    budget_id.value,
                    idempotency_key,
                    reservation_id.value,
                    update_kind.value,
                    None if actual_cost is None else actual_cost.value,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateConflict("idempotency key is already in use") from error

    @staticmethod
    def _require_type(value: object, expected: type, field: str) -> None:
        if not isinstance(value, expected):
            raise TypeError(f"{field} must be {expected.__name__}")

    @staticmethod
    def _require_key(value: object) -> None:
        if not isinstance(value, str):
            raise TypeError("idempotency_key must be a string")
        if not value or len(value) > 256 or any(ord(char) < 0x20 for char in value):
            raise ValueError("idempotency_key must contain 1 to 256 printable characters")
