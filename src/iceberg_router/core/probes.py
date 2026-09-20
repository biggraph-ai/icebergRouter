"""Predeclared, cash-capped probe schedules without learned probe valuation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Mapping, Sequence

from iceberg_router.contracts.identifiers import (
    AccountId, AttemptId, AuthorizationId, BudgetId, DecisionId, OptionId,
    RequestId, ReservationId,
)
from iceberg_router.contracts.money import Nanodollars


class ProbeVariant(str, Enum):
    ZERO = "zero-probe"
    RANDOM = "cash-capped-random-probe"
    STRATIFIED = "cash-capped-stratified-probe"
    RESOURCE_AWARE_RACING = "resource-aware-racing"


@dataclass(frozen=True, slots=True)
class ProbeCandidate:
    request_id: RequestId
    context: str
    option_id: OptionId
    upper_cost: Nanodollars
    uncertainty_rank: int

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, RequestId):
            raise TypeError("request_id must be RequestId")
        if not isinstance(self.context, str) or not self.context:
            raise ValueError("context must be non-empty")
        if not isinstance(self.option_id, OptionId):
            raise TypeError("option_id must be OptionId")
        if not isinstance(self.upper_cost, Nanodollars):
            raise TypeError("upper_cost must be Nanodollars")
        if isinstance(self.uncertainty_rank, bool) or not isinstance(self.uncertainty_rank, int):
            raise TypeError("uncertainty_rank must be an integer")
        if self.uncertainty_rank < 0:
            raise ValueError("uncertainty_rank must be non-negative")


@dataclass(frozen=True, slots=True)
class ProbePlan:
    variant: ProbeVariant
    cap: Nanodollars
    selected: tuple[ProbeCandidate, ...]
    reserved: Nanodollars
    stopping_rule: str


def plan_probes(
    variant: ProbeVariant,
    candidates: Sequence[ProbeCandidate],
    *,
    cap: Nanodollars,
    seed: str,
) -> ProbePlan:
    """Select whole probes before execution and never exceed the cash cap."""
    if not isinstance(variant, ProbeVariant):
        raise TypeError("variant must be ProbeVariant")
    if not isinstance(cap, Nanodollars):
        raise TypeError("cap must be Nanodollars")
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed must be non-empty")
    rows = tuple(candidates)
    if any(not isinstance(row, ProbeCandidate) for row in rows):
        raise TypeError("candidates must contain ProbeCandidate")
    if variant is ProbeVariant.ZERO:
        ordered: tuple[ProbeCandidate, ...] = ()
    elif variant is ProbeVariant.RANDOM:
        ordered = tuple(sorted(rows, key=lambda row: hashlib.sha256(
            f"{seed}:{row.request_id.value}:{row.option_id.value}".encode()).digest()))
    elif variant is ProbeVariant.STRATIFIED:
        ordered = _round_robin(rows, key=lambda row: row.context)
    else:
        # Racing prioritizes uncertain, cheaper strata but does not eliminate any arm.
        ordered = _round_robin(
            sorted(rows, key=lambda row: (-row.uncertainty_rank, row.upper_cost.value)),
            key=lambda row: row.option_id.value,
        )
    selected = []
    reserved = 0
    for row in ordered:
        if reserved + row.upper_cost.value > cap.value:
            continue
        selected.append(row)
        reserved += row.upper_cost.value
    rule = "no probes" if variant is ProbeVariant.ZERO else (
        "predeclared order; stop before the next whole probe would exceed cap"
    )
    return ProbePlan(variant, cap, tuple(selected), Nanodollars(reserved), rule)


def authorize_probe_plan(ledger, plan: ProbePlan, *, budget_id: BudgetId, account_id: AccountId):
    """Create one durable authorization per planned probe under an account cap."""
    if not isinstance(plan, ProbePlan):
        raise TypeError("plan must be ProbePlan")
    records = []
    for index, row in enumerate(plan.selected, start=1):
        identity = hashlib.sha256(
            f"{plan.variant.value}:{row.request_id.value}:{row.option_id.value}:{index}".encode()
        ).hexdigest()[:24]
        records.append(ledger.reserve_and_authorize(
            budget_id=budget_id,
            reservation_id=ReservationId(f"probe-reservation-{identity}"),
            request_id=row.request_id,
            decision_id=DecisionId(f"probe-decision-{identity}"),
            account_id=account_id,
            max_liability=row.upper_cost,
            authorization_id=AuthorizationId(f"probe-authorization-{identity}"),
            attempt_id=AttemptId(f"probe-attempt-{identity}"),
        ))
    return tuple(records)


def _round_robin(rows: Sequence[ProbeCandidate], *, key) -> tuple[ProbeCandidate, ...]:
    groups: dict[str, list[ProbeCandidate]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    result = []
    names = sorted(groups)
    while any(groups.values()):
        for name in names:
            if groups[name]:
                result.append(groups[name].pop(0))
    return tuple(result)
