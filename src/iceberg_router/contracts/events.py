"""Auditable execution and usage event contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._validation import require_exact_keys, require_mapping, require_text, require_utc_timestamp
from .identifiers import (
    AttemptId,
    AuthorizationId,
    DecisionId,
    EventId,
    OptionId,
    RequestId,
    ReservationId,
)
from .money import Nanodollars


class TraceEventKind(str, Enum):
    OPTION_STARTED = "option_started"
    NODE_STARTED = "node_started"
    BRANCH_SELECTED = "branch_selected"
    ATTEMPT_STARTED = "attempt_started"
    ATTEMPT_FINISHED = "attempt_finished"
    INVALID_OUTCOME = "invalid_outcome"
    ADMISSION_DENIED = "admission_denied"
    BUDGET_BREACH = "budget_breach"
    OPTION_FINISHED = "option_finished"
    OPTION_DEFERRED = "option_deferred"
    OPTION_FAILED = "option_failed"


class UsageState(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    event_id: EventId
    request_id: RequestId
    decision_id: DecisionId
    option_id: OptionId
    sequence: int
    kind: TraceEventKind
    occurred_at: str
    detail_code: str
    attempt_id: AttemptId | None = None
    authorization_id: AuthorizationId | None = None

    def __post_init__(self) -> None:
        required_types = (
            (self.event_id, EventId, "event_id"),
            (self.request_id, RequestId, "request_id"),
            (self.decision_id, DecisionId, "decision_id"),
            (self.option_id, OptionId, "option_id"),
        )
        for value, expected, name in required_types:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence must be an integer")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not isinstance(self.kind, TraceEventKind):
            raise TypeError("kind must be TraceEventKind")
        require_utc_timestamp(self.occurred_at, "occurred_at")
        require_text(self.detail_code, "detail_code", maximum=128)
        if self.attempt_id is not None and not isinstance(self.attempt_id, AttemptId):
            raise TypeError("attempt_id must be AttemptId or None")
        if self.authorization_id is not None and not isinstance(
            self.authorization_id, AuthorizationId
        ):
            raise TypeError("authorization_id must be AuthorizationId or None")
        if (self.attempt_id is None) != (self.authorization_id is None):
            raise ValueError("attempt_id and authorization_id must be present together")

    def to_json(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id.to_json(),
            "requestId": self.request_id.to_json(),
            "decisionId": self.decision_id.to_json(),
            "optionId": self.option_id.to_json(),
            "sequence": self.sequence,
            "kind": self.kind.value,
            "occurredAt": self.occurred_at,
            "detailCode": self.detail_code,
            "attemptId": None if self.attempt_id is None else self.attempt_id.to_json(),
            "authorizationId": (
                None if self.authorization_id is None else self.authorization_id.to_json()
            ),
        }

    @classmethod
    def from_json(cls, value: object) -> TraceEvent:
        obj = require_mapping(value, "trace event")
        require_exact_keys(
            obj,
            "trace event",
            {
                "eventId",
                "requestId",
                "decisionId",
                "optionId",
                "sequence",
                "kind",
                "occurredAt",
                "detailCode",
                "attemptId",
                "authorizationId",
            },
        )
        try:
            kind = TraceEventKind(obj["kind"])
        except (TypeError, ValueError) as error:
            raise ValueError("trace event kind is invalid") from error
        attempt = obj["attemptId"]
        authorization = obj["authorizationId"]
        return cls(
            event_id=EventId.from_json(obj["eventId"]),
            request_id=RequestId.from_json(obj["requestId"]),
            decision_id=DecisionId.from_json(obj["decisionId"]),
            option_id=OptionId.from_json(obj["optionId"]),
            sequence=obj["sequence"],
            kind=kind,
            occurred_at=require_text(obj["occurredAt"], "occurredAt"),
            detail_code=require_text(obj["detailCode"], "detailCode", maximum=128),
            attempt_id=None if attempt is None else AttemptId.from_json(attempt),
            authorization_id=(
                None if authorization is None else AuthorizationId.from_json(authorization)
            ),
        )


@dataclass(frozen=True, slots=True)
class UsageEvent:
    event_id: EventId
    request_id: RequestId
    attempt_id: AttemptId
    authorization_id: AuthorizationId
    reservation_id: ReservationId
    state: UsageState
    occurred_at: str
    idempotency_key: str
    amount: Nanodollars | None = None
    provider_receipt: str | None = None

    def __post_init__(self) -> None:
        required_types = (
            (self.event_id, EventId, "event_id"),
            (self.request_id, RequestId, "request_id"),
            (self.attempt_id, AttemptId, "attempt_id"),
            (self.authorization_id, AuthorizationId, "authorization_id"),
            (self.reservation_id, ReservationId, "reservation_id"),
        )
        for value, expected, name in required_types:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        if not isinstance(self.state, UsageState):
            raise TypeError("state must be UsageState")
        require_utc_timestamp(self.occurred_at, "occurred_at")
        require_text(self.idempotency_key, "idempotency_key", maximum=256)
        if self.state is UsageState.KNOWN and not isinstance(self.amount, Nanodollars):
            raise ValueError("known usage requires an amount")
        if self.state is UsageState.UNKNOWN and self.amount is not None:
            raise ValueError("unknown usage cannot carry an amount")
        if self.provider_receipt is not None:
            require_text(self.provider_receipt, "provider_receipt", maximum=1024)

    def to_json(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id.to_json(),
            "requestId": self.request_id.to_json(),
            "attemptId": self.attempt_id.to_json(),
            "authorizationId": self.authorization_id.to_json(),
            "reservationId": self.reservation_id.to_json(),
            "state": self.state.value,
            "occurredAt": self.occurred_at,
            "idempotencyKey": self.idempotency_key,
            "amountNanos": None if self.amount is None else self.amount.to_json(),
            "providerReceipt": self.provider_receipt,
        }

    @classmethod
    def from_json(cls, value: object) -> UsageEvent:
        obj = require_mapping(value, "usage event")
        require_exact_keys(
            obj,
            "usage event",
            {
                "eventId",
                "requestId",
                "attemptId",
                "authorizationId",
                "reservationId",
                "state",
                "occurredAt",
                "idempotencyKey",
                "amountNanos",
                "providerReceipt",
            },
        )
        try:
            state = UsageState(obj["state"])
        except (TypeError, ValueError) as error:
            raise ValueError("usage event state is invalid") from error
        amount_value = obj["amountNanos"]
        receipt = obj["providerReceipt"]
        if receipt is not None and not isinstance(receipt, str):
            raise TypeError("providerReceipt must be a string or null")
        return cls(
            event_id=EventId.from_json(obj["eventId"]),
            request_id=RequestId.from_json(obj["requestId"]),
            attempt_id=AttemptId.from_json(obj["attemptId"]),
            authorization_id=AuthorizationId.from_json(obj["authorizationId"]),
            reservation_id=ReservationId.from_json(obj["reservationId"]),
            state=state,
            occurred_at=require_text(obj["occurredAt"], "occurredAt"),
            idempotency_key=require_text(
                obj["idempotencyKey"], "idempotencyKey", maximum=256
            ),
            amount=None if amount_value is None else Nanodollars.from_json(amount_value),
            provider_receipt=receipt,
        )
