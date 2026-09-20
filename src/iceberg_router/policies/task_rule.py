"""Deterministic workload and task-feature routing controls."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from iceberg_router.contracts.decisions import DecisionRecord
from iceberg_router.contracts.identifiers import OptionId, PolicyVersion, WorkloadId

from .fixed import PolicyConfigurationError, PolicyRequest, _decision


@dataclass(frozen=True, slots=True)
class WorkloadRulePolicy:
    """Route by WorkloadId; this is not represented as task-aware routing."""

    rules: Mapping[WorkloadId, OptionId]
    policy_version: PolicyVersion
    fallback_option_id: OptionId | None = None

    def __post_init__(self) -> None:
        _validate_rules(self, WorkloadId)

    def select(self, request: PolicyRequest) -> DecisionRecord:
        if not isinstance(request, PolicyRequest):
            raise TypeError("request must be PolicyRequest")
        return _select_target(
            request,
            self.policy_version,
            self.rules.get(request.workload_id, self.fallback_option_id),
            "no_workload_rule",
        )


@dataclass(frozen=True, slots=True)
class TaskFeatureRulePolicy:
    """Route by explicit versioned task-family features, not budget grouping."""

    rules: Mapping[str, OptionId]
    policy_version: PolicyVersion
    feature_version: str
    fallback_option_id: OptionId | None = None

    def __post_init__(self) -> None:
        _validate_rules(self, str)
        if not isinstance(self.feature_version, str) or not self.feature_version:
            raise ValueError("feature_version must be a non-empty string")

    def select(self, request: PolicyRequest) -> DecisionRecord:
        if not isinstance(request, PolicyRequest):
            raise TypeError("request must be PolicyRequest")
        if request.task_features.version != self.feature_version:
            raise PolicyConfigurationError("task feature version does not match policy")
        return _select_target(
            request,
            self.policy_version,
            self.rules.get(request.task_features.task_family, self.fallback_option_id),
            "no_task_feature_rule",
        )


def _validate_rules(policy, key_type) -> None:
    if not isinstance(policy.rules, Mapping) or not policy.rules:
        raise PolicyConfigurationError("rules must be a non-empty mapping")
    if any(not isinstance(key, key_type) or (key_type is str and not key) for key in policy.rules):
        raise TypeError("rule keys have the wrong type")
    if any(not isinstance(value, OptionId) for value in policy.rules.values()):
        raise TypeError("rule values must be OptionId values")
    if not isinstance(policy.policy_version, PolicyVersion):
        raise TypeError("policy_version must be PolicyVersion")
    if policy.fallback_option_id is not None and not isinstance(
        policy.fallback_option_id, OptionId
    ):
        raise TypeError("fallback_option_id must be OptionId or None")
    object.__setattr__(policy, "rules", MappingProxyType(dict(policy.rules)))


def _select_target(request, version, target, missing_reason):
    if target is None:
        return _decision(request, version, None, Decimal(1), missing_reason)
    candidate = next((item for item in request.candidates if item.option_id == target), None)
    if candidate is None:
        return _decision(request, version, None, Decimal(1), "rule_option_missing")
    if not candidate.eligible:
        return _decision(request, version, None, Decimal(1), "rule_option_ineligible")
    return _decision(request, version, target, Decimal(1))


# Reviewed compatibility alias. New code should use WorkloadRulePolicy.
TaskRulePolicy = WorkloadRulePolicy
