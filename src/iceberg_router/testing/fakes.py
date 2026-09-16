"""Deterministic, offline operation adapters for contract tests."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from iceberg_router.contracts.adapters import OperationContext, OperationResult


class DeterministicIdentityFactory:
    def __init__(self):
        self._next = 0

    def new_id(self, category: str) -> str:
        self._next += 1
        return f"{category}-{self._next}"


class FixedClock:
    def __init__(self, timestamp: str = "2026-09-15T12:00:00Z"):
        self.timestamp = timestamp

    def now(self) -> str:
        return self.timestamp


@dataclass
class ScriptedAdapter:
    """Return or raise queued steps and retain received contexts."""

    steps: Iterable[OperationResult | Exception]
    calls: list[OperationContext] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._steps = deque(self.steps)

    def execute(self, context: OperationContext) -> OperationResult:
        self.calls.append(context)
        if not self._steps:
            raise AssertionError("scripted adapter has no remaining step")
        step = self._steps.popleft()
        if isinstance(step, Exception):
            raise step
        return step
