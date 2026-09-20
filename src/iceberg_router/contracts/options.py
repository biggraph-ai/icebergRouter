"""Portable definitions for finite, bounded conditional options."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._validation import require_exact_keys, require_mapping, require_text
from .identifiers import (
    AccountId,
    ApplicabilityVersion,
    BoundVersion,
    EstimatorVersion,
    NodeId,
    OptionId,
    OptionVersion,
)
from .money import Nanodollars


class OperationKind(str, Enum):
    MODEL_CALL = "model_call"
    DETERMINISTIC_TOOL = "deterministic_tool"
    VERIFY = "verify"
    RETRIEVAL = "retrieval"


class BranchOutcome(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    UNKNOWN = "unknown"
    INAPPLICABLE = "inapplicable"
    PASS = "pass"
    FAIL = "fail"
    EMPTY = "empty"
    UNFUNDED = "unfunded"


class TerminalStatus(str, Enum):
    COMPLETE = "complete"
    DEFERRED = "deferred"
    FAILED = "failed"


class ArtifactRole(str, Enum):
    ORIGINAL_REQUEST = "original_request"
    CANDIDATE_ANSWER = "candidate_answer"
    RETRIEVED_EVIDENCE = "retrieved_evidence"
    CHECKER_EVIDENCE = "checker_evidence"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True, slots=True)
class ArtifactDeclaration:
    role: ArtifactRole
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, ArtifactRole):
            raise TypeError("role must be ArtifactRole")
        require_text(self.version, "version", maximum=128)

    def to_json(self) -> dict[str, str]:
        return {"role": self.role.value, "version": self.version}

    @classmethod
    def from_json(cls, value: object) -> ArtifactDeclaration:
        obj = require_mapping(value, "artifact declaration")
        require_exact_keys(obj, "artifact declaration", {"role", "version"})
        try:
            role = ArtifactRole(obj["role"])
        except (TypeError, ValueError) as error:
            raise ValueError("artifact role is invalid") from error
        return cls(role, require_text(obj["version"], "version", maximum=128))


@dataclass(frozen=True, slots=True)
class InputBinding:
    input_name: str
    source_node_id: NodeId | None
    role: ArtifactRole

    def __post_init__(self) -> None:
        require_text(self.input_name, "input_name", maximum=128)
        if self.source_node_id is not None and not isinstance(self.source_node_id, NodeId):
            raise TypeError("source_node_id must be NodeId or None")
        if not isinstance(self.role, ArtifactRole):
            raise TypeError("role must be ArtifactRole")
        if self.source_node_id is None and self.role is not ArtifactRole.ORIGINAL_REQUEST:
            raise ValueError("only original_request may use the request source")
        if self.source_node_id is not None and self.role is ArtifactRole.ORIGINAL_REQUEST:
            raise ValueError("original_request must use the request source")

    def to_json(self) -> dict[str, str | None]:
        return {
            "inputName": self.input_name,
            "sourceNodeId": (
                None if self.source_node_id is None else self.source_node_id.to_json()
            ),
            "role": self.role.value,
        }

    @classmethod
    def from_json(cls, value: object) -> InputBinding:
        obj = require_mapping(value, "input binding")
        require_exact_keys(
            obj, "input binding", {"inputName", "sourceNodeId", "role"}
        )
        source = obj["sourceNodeId"]
        try:
            role = ArtifactRole(obj["role"])
        except (TypeError, ValueError) as error:
            raise ValueError("input binding role is invalid") from error
        return cls(
            require_text(obj["inputName"], "inputName", maximum=128),
            None if source is None else NodeId.from_json(source),
            role,
        )


@dataclass(frozen=True, slots=True)
class ApplicabilityRule:
    rule_id: str
    version: ApplicabilityVersion

    def __post_init__(self) -> None:
        require_text(self.rule_id, "rule_id", maximum=128)
        if not isinstance(self.version, ApplicabilityVersion):
            raise TypeError("version must be ApplicabilityVersion")

    def to_json(self) -> dict[str, str]:
        return {"ruleId": self.rule_id, "version": self.version.to_json()}

    @classmethod
    def from_json(cls, value: object) -> ApplicabilityRule:
        obj = require_mapping(value, "applicability rule")
        require_exact_keys(obj, "applicability rule", {"ruleId", "version"})
        return cls(
            require_text(obj["ruleId"], "ruleId", maximum=128),
            ApplicabilityVersion.from_json(obj["version"]),
        )


@dataclass(frozen=True, slots=True)
class OperationLimits:
    max_attempts: int
    timeout_ms: int
    max_input_tokens: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        for value, field, allow_zero in (
            (self.max_attempts, "max_attempts", False),
            (self.timeout_ms, "timeout_ms", False),
            (self.max_input_tokens, "max_input_tokens", True),
            (self.max_output_tokens, "max_output_tokens", True),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")
            minimum = 0 if allow_zero else 1
            if value < minimum or value > (1 << 31) - 1:
                raise ValueError(f"{field} must be between {minimum} and 2147483647")

    def to_json(self) -> dict[str, int]:
        return {
            "maxAttempts": self.max_attempts,
            "timeoutMs": self.timeout_ms,
            "maxInputTokens": self.max_input_tokens,
            "maxOutputTokens": self.max_output_tokens,
        }

    @classmethod
    def from_json(cls, value: object) -> OperationLimits:
        obj = require_mapping(value, "operation limits")
        require_exact_keys(
            obj,
            "operation limits",
            {"maxAttempts", "timeoutMs", "maxInputTokens", "maxOutputTokens"},
        )
        return cls(
            max_attempts=obj["maxAttempts"],
            timeout_ms=obj["timeoutMs"],
            max_input_tokens=obj["maxInputTokens"],
            max_output_tokens=obj["maxOutputTokens"],
        )


@dataclass(frozen=True, slots=True)
class Branch:
    outcome: BranchOutcome
    target: NodeId

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, BranchOutcome):
            raise TypeError("outcome must be BranchOutcome")
        if not isinstance(self.target, NodeId):
            raise TypeError("target must be NodeId")

    def to_json(self) -> dict[str, str]:
        return {"outcome": self.outcome.value, "target": self.target.to_json()}

    @classmethod
    def from_json(cls, value: object) -> Branch:
        obj = require_mapping(value, "branch")
        require_exact_keys(obj, "branch", {"outcome", "target"})
        try:
            outcome = BranchOutcome(obj["outcome"])
        except (TypeError, ValueError) as error:
            raise ValueError("branch outcome is invalid") from error
        return cls(outcome, NodeId.from_json(obj["target"]))


@dataclass(frozen=True, slots=True)
class OperationNode:
    node_id: NodeId
    kind: OperationKind
    account_id: AccountId
    liability_bound: Nanodollars
    limits: OperationLimits
    operation_version: str
    branches: tuple[Branch, ...]
    input_bindings: tuple[InputBinding, ...]
    output: ArtifactDeclaration | None

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, NodeId):
            raise TypeError("node_id must be NodeId")
        if not isinstance(self.kind, OperationKind):
            raise TypeError("kind must be OperationKind")
        if not isinstance(self.account_id, AccountId):
            raise TypeError("account_id must be AccountId")
        if not isinstance(self.liability_bound, Nanodollars):
            raise TypeError("liability_bound must be Nanodollars")
        if not isinstance(self.limits, OperationLimits):
            raise TypeError("limits must be OperationLimits")
        require_text(self.operation_version, "operation_version", maximum=128)
        if not isinstance(self.branches, tuple) or not self.branches:
            raise ValueError("branches must be a non-empty tuple")
        if any(not isinstance(branch, Branch) for branch in self.branches):
            raise TypeError("branches must contain Branch values")
        outcomes = [branch.outcome for branch in self.branches]
        if len(outcomes) != len(set(outcomes)):
            raise ValueError("branch outcomes must be unique within a node")
        if not isinstance(self.input_bindings, tuple):
            raise TypeError("input_bindings must be a tuple")
        if any(not isinstance(binding, InputBinding) for binding in self.input_bindings):
            raise TypeError("input_bindings must contain InputBinding values")
        names = [binding.input_name for binding in self.input_bindings]
        if len(names) != len(set(names)):
            raise ValueError("input binding names must be unique within a node")
        if self.output is not None and not isinstance(self.output, ArtifactDeclaration):
            raise TypeError("output must be ArtifactDeclaration or None")

    def to_json(self) -> dict[str, Any]:
        return {
            "nodeType": "operation",
            "nodeId": self.node_id.to_json(),
            "kind": self.kind.value,
            "accountId": self.account_id.to_json(),
            "liabilityBoundNanos": self.liability_bound.to_json(),
            "limits": self.limits.to_json(),
            "operationVersion": self.operation_version,
            "branches": [branch.to_json() for branch in self.branches],
            "inputBindings": [binding.to_json() for binding in self.input_bindings],
            "output": None if self.output is None else self.output.to_json(),
        }

    @classmethod
    def from_json(cls, value: object) -> OperationNode:
        obj = require_mapping(value, "operation node")
        require_exact_keys(
            obj,
            "operation node",
            {
                "nodeType",
                "nodeId",
                "kind",
                "accountId",
                "liabilityBoundNanos",
                "limits",
                "operationVersion",
                "branches",
                "inputBindings",
                "output",
            },
        )
        if obj["nodeType"] != "operation":
            raise ValueError("operation nodeType must be 'operation'")
        try:
            kind = OperationKind(obj["kind"])
        except (TypeError, ValueError) as error:
            raise ValueError("operation kind is invalid") from error
        branches = obj["branches"]
        if not isinstance(branches, list):
            raise TypeError("branches must be an array")
        input_bindings = obj["inputBindings"]
        if not isinstance(input_bindings, list):
            raise TypeError("inputBindings must be an array")
        return cls(
            node_id=NodeId.from_json(obj["nodeId"]),
            kind=kind,
            account_id=AccountId.from_json(obj["accountId"]),
            liability_bound=Nanodollars.from_json(obj["liabilityBoundNanos"]),
            limits=OperationLimits.from_json(obj["limits"]),
            operation_version=require_text(
                obj["operationVersion"], "operationVersion", maximum=128
            ),
            branches=tuple(Branch.from_json(branch) for branch in branches),
            input_bindings=tuple(
                InputBinding.from_json(binding) for binding in input_bindings
            ),
            output=(
                None
                if obj["output"] is None
                else ArtifactDeclaration.from_json(obj["output"])
            ),
        )


@dataclass(frozen=True, slots=True)
class TerminalNode:
    node_id: NodeId
    status: TerminalStatus
    result_code: str
    answer_binding: InputBinding | None

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, NodeId):
            raise TypeError("node_id must be NodeId")
        if not isinstance(self.status, TerminalStatus):
            raise TypeError("status must be TerminalStatus")
        require_text(self.result_code, "result_code", maximum=128)
        if self.answer_binding is not None and not isinstance(
            self.answer_binding, InputBinding
        ):
            raise TypeError("answer_binding must be InputBinding or None")
        if self.status is TerminalStatus.COMPLETE and self.answer_binding is None:
            raise ValueError("complete terminal requires an answer binding")
        if (
            self.answer_binding is not None
            and self.answer_binding.role is not ArtifactRole.CANDIDATE_ANSWER
        ):
            raise ValueError("terminal answer binding must select a candidate answer")

    def to_json(self) -> dict[str, str]:
        return {
            "nodeType": "terminal",
            "nodeId": self.node_id.to_json(),
            "status": self.status.value,
            "resultCode": self.result_code,
            "answerBinding": (
                None if self.answer_binding is None else self.answer_binding.to_json()
            ),
        }

    @classmethod
    def from_json(cls, value: object) -> TerminalNode:
        obj = require_mapping(value, "terminal node")
        require_exact_keys(
            obj,
            "terminal node",
            {"nodeType", "nodeId", "status", "resultCode", "answerBinding"},
        )
        if obj["nodeType"] != "terminal":
            raise ValueError("terminal nodeType must be 'terminal'")
        try:
            status = TerminalStatus(obj["status"])
        except (TypeError, ValueError) as error:
            raise ValueError("terminal status is invalid") from error
        return cls(
            NodeId.from_json(obj["nodeId"]),
            status,
            require_text(obj["resultCode"], "resultCode", maximum=128),
            None
            if obj["answerBinding"] is None
            else InputBinding.from_json(obj["answerBinding"]),
        )


OptionNode = OperationNode | TerminalNode


@dataclass(frozen=True, slots=True)
class OptionDefinition:
    option_id: OptionId
    version: OptionVersion
    entry_node_id: NodeId
    applicability: ApplicabilityRule
    expected_cost_estimator_version: EstimatorVersion
    bound_calculator_version: BoundVersion
    max_transitions: int
    max_total_attempts: int
    nodes: tuple[OptionNode, ...]
    schema_version: str = "1"

    def __post_init__(self) -> None:
        for value, expected, field in (
            (self.option_id, OptionId, "option_id"),
            (self.version, OptionVersion, "version"),
            (self.entry_node_id, NodeId, "entry_node_id"),
            (self.applicability, ApplicabilityRule, "applicability"),
            (
                self.expected_cost_estimator_version,
                EstimatorVersion,
                "expected_cost_estimator_version",
            ),
            (self.bound_calculator_version, BoundVersion, "bound_calculator_version"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field} must be {expected.__name__}")
        for value, field in (
            (self.max_transitions, "max_transitions"),
            (self.max_total_attempts, "max_total_attempts"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")
            if value < 0 or value > (1 << 31) - 1:
                raise ValueError(f"{field} must be between 0 and 2147483647")
        if not isinstance(self.nodes, tuple) or not self.nodes:
            raise ValueError("nodes must be a non-empty tuple")
        if any(not isinstance(node, (OperationNode, TerminalNode)) for node in self.nodes):
            raise TypeError("nodes must contain operation or terminal nodes")
        if self.schema_version != "1":
            raise ValueError("unsupported option schema_version")

    def to_json(self) -> dict[str, Any]:
        return {
            "optionId": self.option_id.to_json(),
            "version": self.version.to_json(),
            "entryNodeId": self.entry_node_id.to_json(),
            "applicability": self.applicability.to_json(),
            "expectedCostEstimatorVersion": self.expected_cost_estimator_version.to_json(),
            "boundCalculatorVersion": self.bound_calculator_version.to_json(),
            "maxTransitions": self.max_transitions,
            "maxTotalAttempts": self.max_total_attempts,
            "nodes": [node.to_json() for node in self.nodes],
            "schemaVersion": self.schema_version,
        }

    @classmethod
    def from_json(cls, value: object) -> OptionDefinition:
        obj = require_mapping(value, "option definition")
        require_exact_keys(
            obj,
            "option definition",
            {
                "optionId",
                "version",
                "entryNodeId",
                "applicability",
                "expectedCostEstimatorVersion",
                "boundCalculatorVersion",
                "maxTransitions",
                "maxTotalAttempts",
                "nodes",
                "schemaVersion",
            },
        )
        raw_nodes = obj["nodes"]
        if not isinstance(raw_nodes, list):
            raise TypeError("nodes must be an array")
        nodes: list[OptionNode] = []
        for raw_node in raw_nodes:
            node_obj = require_mapping(raw_node, "option node")
            node_type = node_obj.get("nodeType")
            if node_type == "operation":
                nodes.append(OperationNode.from_json(node_obj))
            elif node_type == "terminal":
                nodes.append(TerminalNode.from_json(node_obj))
            else:
                raise ValueError("option node has an invalid nodeType")
        return cls(
            option_id=OptionId.from_json(obj["optionId"]),
            version=OptionVersion.from_json(obj["version"]),
            entry_node_id=NodeId.from_json(obj["entryNodeId"]),
            applicability=ApplicabilityRule.from_json(obj["applicability"]),
            expected_cost_estimator_version=EstimatorVersion.from_json(
                obj["expectedCostEstimatorVersion"]
            ),
            bound_calculator_version=BoundVersion.from_json(obj["boundCalculatorVersion"]),
            max_transitions=obj["maxTransitions"],
            max_total_attempts=obj["maxTotalAttempts"],
            nodes=tuple(nodes),
            schema_version=require_text(
                obj["schemaVersion"], "schemaVersion", maximum=16
            ),
        )
