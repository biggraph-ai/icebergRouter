"""Frozen resource identities and reviewed bound evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._validation import require_exact_keys, require_mapping, require_text
from .money import Nanodollars


@dataclass(frozen=True, slots=True)
class ResourceIdentity:
    provider: str
    resource: str
    revision: str
    prompt_revision: str
    checker_revision: str | None = None

    def __post_init__(self) -> None:
        for value, field in (
            (self.provider, "provider"),
            (self.resource, "resource"),
            (self.revision, "revision"),
            (self.prompt_revision, "prompt_revision"),
        ):
            require_text(value, field, maximum=128)
        if self.checker_revision is not None:
            require_text(self.checker_revision, "checker_revision", maximum=128)

    @property
    def key(self) -> str:
        checker = self.checker_revision or "none"
        return f"{self.provider}/{self.resource}@{self.revision}:{self.prompt_revision}:{checker}"

    def to_json(self) -> dict[str, str | None]:
        return {
            "provider": self.provider,
            "resource": self.resource,
            "revision": self.revision,
            "promptRevision": self.prompt_revision,
            "checkerRevision": self.checker_revision,
        }

    @classmethod
    def from_json(cls, value: object) -> ResourceIdentity:
        obj = require_mapping(value, "resource identity")
        require_exact_keys(
            obj,
            "resource identity",
            {"provider", "resource", "revision", "promptRevision", "checkerRevision"},
        )
        checker = obj["checkerRevision"]
        return cls(
            require_text(obj["provider"], "provider", maximum=128),
            require_text(obj["resource"], "resource", maximum=128),
            require_text(obj["revision"], "revision", maximum=128),
            require_text(obj["promptRevision"], "promptRevision", maximum=128),
            None if checker is None else require_text(checker, "checkerRevision", maximum=128),
        )


@dataclass(frozen=True, slots=True)
class BoundedContractEvidence:
    evidence_version: str
    tariff_version: str
    calculator_version: str
    attempt_bound: Nanodollars
    reviewed: bool
    hidden_retries_disabled: bool
    enforced_limits: bool

    def __post_init__(self) -> None:
        for value, field in (
            (self.evidence_version, "evidence_version"),
            (self.tariff_version, "tariff_version"),
            (self.calculator_version, "calculator_version"),
        ):
            require_text(value, field, maximum=128)
        if not isinstance(self.attempt_bound, Nanodollars):
            raise TypeError("attempt_bound must be Nanodollars")
        for value, field in (
            (self.reviewed, "reviewed"),
            (self.hidden_retries_disabled, "hidden_retries_disabled"),
            (self.enforced_limits, "enforced_limits"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{field} must be bool")

    @property
    def strict_eligible(self) -> bool:
        return self.reviewed and self.hidden_retries_disabled and self.enforced_limits

    def to_json(self) -> dict[str, Any]:
        return {
            "evidenceVersion": self.evidence_version,
            "tariffVersion": self.tariff_version,
            "calculatorVersion": self.calculator_version,
            "attemptBoundNanos": self.attempt_bound.to_json(),
            "reviewed": self.reviewed,
            "hiddenRetriesDisabled": self.hidden_retries_disabled,
            "enforcedLimits": self.enforced_limits,
        }

    @classmethod
    def from_json(cls, value: object) -> BoundedContractEvidence:
        obj = require_mapping(value, "bounded contract evidence")
        require_exact_keys(
            obj,
            "bounded contract evidence",
            {
                "evidenceVersion", "tariffVersion", "calculatorVersion", "reviewed",
                "hiddenRetriesDisabled", "enforcedLimits", "attemptBoundNanos",
            },
        )
        return cls(
            require_text(obj["evidenceVersion"], "evidenceVersion", maximum=128),
            require_text(obj["tariffVersion"], "tariffVersion", maximum=128),
            require_text(obj["calculatorVersion"], "calculatorVersion", maximum=128),
            Nanodollars.from_json(obj["attemptBoundNanos"]),
            obj["reviewed"], obj["hiddenRetriesDisabled"], obj["enforcedLimits"],
        )
