"""Upper-liability admission boundary for the durable budget ledger."""

from __future__ import annotations

from dataclasses import dataclass

from iceberg_router.contracts.decisions import CostEstimate, EstimateState
from iceberg_router.contracts.identifiers import (
    AccountId,
    AttemptId,
    AuthorizationId,
    BudgetId,
    DecisionId,
    RequestId,
    ReservationId,
)

from .ledger import AuthorizationRecord, ReservationRecord, SQLiteBudgetLedger


@dataclass(frozen=True, slots=True)
class AdmissionRequest:
    budget_id: BudgetId
    reservation_id: ReservationId
    request_id: RequestId
    decision_id: DecisionId
    account_id: AccountId
    upper_liability: CostEstimate


@dataclass(frozen=True, slots=True)
class AuthorizedAttempt:
    reservation: ReservationRecord
    authorization: AuthorizationRecord


class BoundUnavailable(ValueError):
    """Admission cannot proceed without a known upper liability."""


class BudgetGovernor:
    """Separates upper-liability admission from expected-cost selection."""

    def __init__(self, ledger: SQLiteBudgetLedger):
        if not isinstance(ledger, SQLiteBudgetLedger):
            raise TypeError("ledger must be SQLiteBudgetLedger")
        self.ledger = ledger

    def reserve(self, request: AdmissionRequest) -> ReservationRecord:
        if not isinstance(request, AdmissionRequest):
            raise TypeError("request must be AdmissionRequest")
        estimate = request.upper_liability
        if not isinstance(estimate, CostEstimate):
            raise TypeError("upper_liability must be CostEstimate")
        if estimate.state is not EstimateState.KNOWN or estimate.amount is None:
            raise BoundUnavailable("strict admission requires a known upper liability")
        return self.ledger.reserve(
            budget_id=request.budget_id,
            reservation_id=request.reservation_id,
            request_id=request.request_id,
            decision_id=request.decision_id,
            account_id=request.account_id,
            max_liability=estimate.amount,
        )

    def authorize(
        self,
        request: AdmissionRequest,
        *,
        authorization_id: AuthorizationId,
        attempt_id: AttemptId,
    ) -> AuthorizedAttempt:
        if not isinstance(request, AdmissionRequest):
            raise TypeError("request must be AdmissionRequest")
        estimate = request.upper_liability
        if not isinstance(estimate, CostEstimate):
            raise TypeError("upper_liability must be CostEstimate")
        if estimate.state is not EstimateState.KNOWN or estimate.amount is None:
            raise BoundUnavailable("strict admission requires a known upper liability")
        reservation, authorization = self.ledger.reserve_and_authorize(
            budget_id=request.budget_id,
            reservation_id=request.reservation_id,
            request_id=request.request_id,
            decision_id=request.decision_id,
            account_id=request.account_id,
            max_liability=estimate.amount,
            authorization_id=authorization_id,
            attempt_id=attempt_id,
        )
        return AuthorizedAttempt(reservation, authorization)
