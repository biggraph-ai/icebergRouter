"""Immutable, restricted-ASCII identifiers for portable records."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TypeVar


_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
IdentifierT = TypeVar("IdentifierT", bound="Identifier")


@dataclass(frozen=True, order=True, slots=True)
class Identifier:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("identifier must be a string")
        if not _IDENTIFIER_PATTERN.fullmatch(self.value):
            raise ValueError(
                "identifier must start with an ASCII letter and contain at most "
                "128 ASCII letters, digits, '.', '_', ':', or '-'"
            )

    @classmethod
    def from_json(cls: type[IdentifierT], value: object) -> IdentifierT:
        if not isinstance(value, str):
            raise TypeError("identifier JSON value must be a string")
        return cls(value)

    def to_json(self) -> str:
        return self.value


class RequestId(Identifier):
    pass


class WorkloadId(Identifier):
    pass


class DecisionId(Identifier):
    pass


class OptionId(Identifier):
    pass


class PolicyVersion(Identifier):
    pass


class SnapshotVersion(Identifier):
    pass


class AttemptId(Identifier):
    pass


class AuthorizationId(Identifier):
    pass


class ReservationId(Identifier):
    pass


class BudgetId(Identifier):
    pass


class EventId(Identifier):
    pass


class OutputId(Identifier):
    pass


class AccountId(Identifier):
    pass


class EvaluatorVersion(Identifier):
    pass
