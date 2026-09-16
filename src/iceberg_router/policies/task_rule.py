"""Deterministic workload-to-option control policy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from iceberg_router.contracts.decisions import DecisionRecord
from iceberg_router.contracts.identifiers import OptionId, PolicyVersion, WorkloadId

from .fixed import PolicyConfigurationError, PolicyRequest, _decision


@dataclass(frozen=True, slots=True)
class TaskRulePolicy:
    rules: Mapping[WorkloadId, OptionId]
    policy_version: PolicyVersion
    fallback_option_id: OptionId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rules, Mapping):
            raise TypeError("rules must be a mapping")
        if not self.rules:
            raise PolicyConfigurationError("rules must not be empty")
        if any(not isinstance(key, WorkloadId) for key in self.rules):
            raise TypeError("rule keys must be WorkloadId values")
        if any(not isinstance(value, OptionId) for value in self.rules.values()):
            raise TypeError("rule values must be OptionId values")
        if not isinstance(self.policy_version, PolicyVersion):
            raise TypeError("policy_version must be PolicyVersion")
        if self.fallback_option_id is not None and not isinstance(
            self.fallback_option_id, OptionId
        ):
            raise TypeError("fallback_option_id must be OptionId or None")
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))

    def select(self, request: PolicyRequest) -> DecisionRecord:
        if not isinstance(request, PolicyRequest):
            raise TypeError("request must be PolicyRequest")
        target = self.rules.get(request.workload_id, self.fallback_option_id)
        if target is None:
            return _decision(
                request, self.policy_version, None, Decimal(1), "no_task_rule"
            )
        candidate = next(
            (item for item in request.candidates if item.option_id == target), None
        )
        if candidate is None:
            return _decision(
                request, self.policy_version, None, Decimal(1), "rule_option_missing"
            )
        if not candidate.eligible:
            return _decision(
                request, self.policy_version, None, Decimal(1), "rule_option_ineligible"
            )
        return _decision(request, self.policy_version, target, Decimal(1))
