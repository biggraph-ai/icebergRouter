"""Independent user-preference, objective, and checker observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._validation import (
    parse_utc_timestamp,
    require_exact_keys,
    require_mapping,
    require_text,
)
from .identifiers import EventId, EvaluatorVersion, OutputId, RequestId


class UserVote(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"
    MISSING = "missing"


class ObjectiveResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class CheckerResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_RUN = "not_run"


@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    event_id: EventId
    request_id: RequestId
    output_id: OutputId
    user_vote: UserVote
    objective_result: ObjectiveResult
    checker_result: CheckerResult
    provenance: str
    evaluator_version: EvaluatorVersion
    observed_at: str
    visible_at: str

    def __post_init__(self) -> None:
        required_types = (
            (self.event_id, EventId, "event_id"),
            (self.request_id, RequestId, "request_id"),
            (self.output_id, OutputId, "output_id"),
            (self.evaluator_version, EvaluatorVersion, "evaluator_version"),
        )
        for value, expected, name in required_types:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        enum_fields = (
            (self.user_vote, UserVote, "user_vote"),
            (self.objective_result, ObjectiveResult, "objective_result"),
            (self.checker_result, CheckerResult, "checker_result"),
        )
        for value, expected, name in enum_fields:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        require_text(self.provenance, "provenance", maximum=512)
        observed = parse_utc_timestamp(self.observed_at, "observed_at")
        visible = parse_utc_timestamp(self.visible_at, "visible_at")
        if visible < observed:
            raise ValueError("visible_at cannot precede observed_at")

    def to_json(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id.to_json(),
            "requestId": self.request_id.to_json(),
            "outputId": self.output_id.to_json(),
            "userVote": self.user_vote.value,
            "objectiveResult": self.objective_result.value,
            "checkerResult": self.checker_result.value,
            "provenance": self.provenance,
            "evaluatorVersion": self.evaluator_version.to_json(),
            "observedAt": self.observed_at,
            "visibleAt": self.visible_at,
        }

    @classmethod
    def from_json(cls, value: object) -> FeedbackEvent:
        obj = require_mapping(value, "feedback event")
        require_exact_keys(
            obj,
            "feedback event",
            {
                "eventId",
                "requestId",
                "outputId",
                "userVote",
                "objectiveResult",
                "checkerResult",
                "provenance",
                "evaluatorVersion",
                "observedAt",
                "visibleAt",
            },
        )
        try:
            user_vote = UserVote(obj["userVote"])
            objective = ObjectiveResult(obj["objectiveResult"])
            checker = CheckerResult(obj["checkerResult"])
        except (TypeError, ValueError) as error:
            raise ValueError("feedback event contains an invalid observation state") from error
        return cls(
            event_id=EventId.from_json(obj["eventId"]),
            request_id=RequestId.from_json(obj["requestId"]),
            output_id=OutputId.from_json(obj["outputId"]),
            user_vote=user_vote,
            objective_result=objective,
            checker_result=checker,
            provenance=require_text(obj["provenance"], "provenance", maximum=512),
            evaluator_version=EvaluatorVersion.from_json(obj["evaluatorVersion"]),
            observed_at=require_text(obj["observedAt"], "observedAt"),
            visible_at=require_text(obj["visibleAt"], "visibleAt"),
        )
