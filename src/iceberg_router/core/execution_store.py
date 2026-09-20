"""Durable request ownership, replay state, and execution transitions."""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from iceberg_router.contracts._validation import require_text
from iceberg_router.contracts.adapters import ArtifactReference, OperationResult
from iceberg_router.contracts.decisions import DecisionRecord
from iceberg_router.contracts.events import TraceEvent, UsageState
from iceberg_router.contracts.identifiers import (
    AttemptId, AuthorizationId, NodeId, RequestId, ReservationId,
)
from iceberg_router.contracts.money import Nanodollars
from iceberg_router.contracts.options import BranchOutcome, TerminalStatus

from .executor import AttemptExecution, ExecutionResult


class ExecutionConflict(RuntimeError):
    """A request identity was reused with behavior-affecting content."""


class ExecutionClaimState(str, Enum):
    OWNER = "owner"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    state: ExecutionClaimState
    result: tuple[DecisionRecord, ExecutionResult | None] | None = None


class SQLiteExecutionStore:
    """Single-host execution ownership and append-only transition storage."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
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
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    request_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_json TEXT NULL
                );
                CREATE TABLE IF NOT EXISTS execution_transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    transition TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def claim(self, request_id: RequestId, fingerprint: str) -> ExecutionClaim:
        if not isinstance(request_id, RequestId):
            raise TypeError("request_id must be RequestId")
        require_text(fingerprint, "fingerprint", maximum=128)
        with self._write() as connection:
            row = connection.execute(
                "SELECT * FROM executions WHERE request_id = ?", (request_id.value,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO executions VALUES (?, ?, 'in_progress', NULL)",
                    (request_id.value, fingerprint),
                )
                return ExecutionClaim(ExecutionClaimState.OWNER)
            if row["fingerprint"] != fingerprint:
                raise ExecutionConflict("request identity conflicts with canonical content")
            if row["state"] == "completed":
                return ExecutionClaim(
                    ExecutionClaimState.COMPLETED,
                    _result_from_json(json.loads(row["result_json"])),
                )
            if row["state"] == "unknown":
                return ExecutionClaim(ExecutionClaimState.UNKNOWN)
            return ExecutionClaim(ExecutionClaimState.IN_PROGRESS)

    def complete(
        self,
        request_id: RequestId,
        fingerprint: str,
        decision: DecisionRecord,
        execution: ExecutionResult | None,
    ) -> None:
        encoded = json.dumps(
            _result_to_json(decision, execution), sort_keys=True, separators=(",", ":")
        )
        with self._write() as connection:
            row = connection.execute(
                "SELECT fingerprint, state FROM executions WHERE request_id = ?",
                (request_id.value,),
            ).fetchone()
            if row is None or row["fingerprint"] != fingerprint:
                raise ExecutionConflict("execution claim is missing or conflicting")
            if row["state"] == "completed":
                existing = connection.execute(
                    "SELECT result_json FROM executions WHERE request_id = ?",
                    (request_id.value,),
                ).fetchone()["result_json"]
                if existing != encoded:
                    raise ExecutionConflict("completed execution content conflicts")
                return
            connection.execute(
                "UPDATE executions SET state = 'completed', result_json = ? WHERE request_id = ?",
                (encoded, request_id.value),
            )

    def mark_unknown(self, request_id: RequestId) -> None:
        with self._write() as connection:
            connection.execute(
                "UPDATE executions SET state = 'unknown' "
                "WHERE request_id = ? AND state = 'in_progress'",
                (request_id.value,),
            )

    def append_transition(self, request_id: RequestId, transition: str, payload: dict) -> None:
        require_text(transition, "transition", maximum=64)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._write() as connection:
            connection.execute(
                "INSERT INTO execution_transitions"
                "(request_id, transition, payload_json) VALUES (?, ?, ?)",
                (request_id.value, transition, encoded),
            )

    def transitions(self, request_id: RequestId) -> tuple[tuple[str, dict], ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT transition, payload_json FROM execution_transitions "
                "WHERE request_id = ? ORDER BY sequence",
                (request_id.value,),
            ).fetchall()
        return tuple((row["transition"], json.loads(row["payload_json"])) for row in rows)

    def record_reconciliation(self, request_id: RequestId, payload: dict) -> None:
        """Persist provider reconciliation evidence without creating new authority."""

        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        self.append_transition(request_id, "reconciled", payload)


def _execution_to_json(result: ExecutionResult) -> dict:
    return {
        "status": result.status.value,
        "resultCode": result.result_code,
        "terminalNodeId": (
            None if result.terminal_node_id is None else result.terminal_node_id.value
        ),
        "outputReference": result.output_reference,
        "attempts": [
            {
                "nodeId": item.node_id.value,
                "attemptNumber": item.attempt_number,
                "attemptId": item.attempt_id.value,
                "authorizationId": item.authorization_id.value,
                "reservationId": item.reservation_id.value,
                "result": {
                    "outcome": item.result.outcome.value,
                    "usageState": item.result.usage_state.value,
                    "actualCostNanos": (
                        None
                        if item.result.actual_cost is None
                        else item.result.actual_cost.to_json()
                    ),
                    "outputReference": item.result.output_reference,
                    "providerReceipt": item.result.provider_receipt,
                },
            }
            for item in result.attempts
        ],
        "trace": [item.to_json() for item in result.trace],
        "artifacts": [item.to_json() for item in result.artifacts],
    }


def _result_to_json(decision: DecisionRecord, execution: ExecutionResult | None) -> dict:
    return {
        "decision": decision.to_json(),
        "execution": None if execution is None else _execution_to_json(execution),
    }


def _result_from_json(value: dict) -> tuple[DecisionRecord, ExecutionResult | None]:
    decision = DecisionRecord.from_json(value["decision"])
    raw = value["execution"]
    if raw is None:
        return decision, None
    attempts = []
    for item in raw["attempts"]:
        result = item["result"]
        actual = result["actualCostNanos"]
        attempts.append(AttemptExecution(
            NodeId(item["nodeId"]), item["attemptNumber"], AttemptId(item["attemptId"]),
            AuthorizationId(item["authorizationId"]), ReservationId(item["reservationId"]),
            OperationResult(
                BranchOutcome(result["outcome"]), UsageState(result["usageState"]),
                None if actual is None else Nanodollars.from_json(actual),
                result["outputReference"], result["providerReceipt"],
            ),
        ))
    execution = ExecutionResult(
        TerminalStatus(raw["status"]), raw["resultCode"],
        None if raw["terminalNodeId"] is None else NodeId(raw["terminalNodeId"]),
        raw["outputReference"], tuple(attempts),
        tuple(TraceEvent.from_json(item) for item in raw["trace"]),
        tuple(ArtifactReference.from_json(item) for item in raw["artifacts"]),
    )
    return decision, execution
