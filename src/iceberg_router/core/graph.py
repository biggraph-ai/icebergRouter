"""Validation and conservative bounds for finite conditional option graphs."""

from __future__ import annotations

from dataclasses import dataclass

from iceberg_router.contracts.identifiers import NodeId
from iceberg_router.contracts.money import Nanodollars
from iceberg_router.contracts.options import (
    BranchOutcome,
    OperationKind,
    OperationNode,
    OptionDefinition,
    OptionNode,
    TerminalNode,
    TerminalStatus,
)


class GraphValidationError(ValueError):
    """An option graph is ambiguous, incomplete, unreachable, or unbounded."""


@dataclass(frozen=True, slots=True)
class ValidatedOption:
    definition: OptionDefinition
    max_path_transitions: int
    max_path_attempts: int
    max_path_liability: Nanodollars
    terminal_statuses: tuple[TerminalStatus, ...]


@dataclass(frozen=True, slots=True)
class _PathBound:
    transitions: int
    attempts: int
    liability: Nanodollars


_REQUIRED_OUTCOMES = {
    OperationKind.MODEL_CALL: frozenset(
        {
            BranchOutcome.SUCCESS,
            BranchOutcome.ERROR,
            BranchOutcome.UNKNOWN,
            BranchOutcome.UNFUNDED,
        }
    ),
    OperationKind.DETERMINISTIC_TOOL: frozenset(
        {
            BranchOutcome.SUCCESS,
            BranchOutcome.ERROR,
            BranchOutcome.UNKNOWN,
            BranchOutcome.INAPPLICABLE,
            BranchOutcome.UNFUNDED,
        }
    ),
    OperationKind.VERIFY: frozenset(
        {
            BranchOutcome.PASS,
            BranchOutcome.FAIL,
            BranchOutcome.UNKNOWN,
            BranchOutcome.ERROR,
            BranchOutcome.UNFUNDED,
        }
    ),
    OperationKind.RETRIEVAL: frozenset(
        {
            BranchOutcome.SUCCESS,
            BranchOutcome.EMPTY,
            BranchOutcome.UNKNOWN,
            BranchOutcome.ERROR,
            BranchOutcome.UNFUNDED,
        }
    ),
}


def validate_option(definition: OptionDefinition) -> ValidatedOption:
    """Validate a frozen option and calculate its worst legal path.

    Increment 3 deliberately admits only directed acyclic graphs. An operation's
    liability bound is per attempt, so its contribution is multiplied by its
    declared maximum attempts. This is structural validation, not proof that an
    external provider honors the declared monetary bound.
    """

    if not isinstance(definition, OptionDefinition):
        raise TypeError("definition must be OptionDefinition")

    nodes: dict[NodeId, OptionNode] = {}
    for node in definition.nodes:
        if node.node_id in nodes:
            raise GraphValidationError(f"duplicate node ID: {node.node_id.value}")
        nodes[node.node_id] = node
    if definition.entry_node_id not in nodes:
        raise GraphValidationError("entry node does not exist")

    for node in definition.nodes:
        if isinstance(node, TerminalNode):
            continue
        actual_outcomes = frozenset(branch.outcome for branch in node.branches)
        required_outcomes = _REQUIRED_OUTCOMES[node.kind]
        if actual_outcomes != required_outcomes:
            missing = sorted(outcome.value for outcome in required_outcomes - actual_outcomes)
            extra = sorted(outcome.value for outcome in actual_outcomes - required_outcomes)
            raise GraphValidationError(
                f"node {node.node_id.value} has missing outcomes {missing} and extra outcomes {extra}"
            )
        for branch in node.branches:
            if branch.target not in nodes:
                raise GraphValidationError(
                    f"node {node.node_id.value} targets missing node {branch.target.value}"
                )

    predecessors: dict[NodeId, set[NodeId]] = {node_id: set() for node_id in nodes}
    for node in definition.nodes:
        if isinstance(node, OperationNode):
            for branch in node.branches:
                predecessors[branch.target].add(node.node_id)

    dominators: dict[NodeId, set[NodeId]] = {
        node_id: ({node_id} if node_id == definition.entry_node_id else set(nodes))
        for node_id in nodes
    }
    changed = True
    while changed:
        changed = False
        for node_id in nodes:
            if node_id == definition.entry_node_id:
                continue
            incoming = predecessors[node_id]
            common = (
                set.intersection(*(dominators[parent] for parent in incoming))
                if incoming
                else set()
            )
            updated = {node_id} | common
            if updated != dominators[node_id]:
                dominators[node_id] = updated
                changed = True

    visiting: set[NodeId] = set()
    visited: set[NodeId] = set()
    memo: dict[NodeId, _PathBound] = {}

    def path_bound(node_id: NodeId) -> _PathBound:
        if node_id in visiting:
            raise GraphValidationError(f"cycle detected at node {node_id.value}")
        if node_id in memo:
            return memo[node_id]
        visiting.add(node_id)
        visited.add(node_id)
        node = nodes[node_id]
        if isinstance(node, TerminalNode):
            bound = _PathBound(0, 0, Nanodollars(0))
        else:
            children = [path_bound(branch.target) for branch in node.branches]
            child_transitions = max(child.transitions for child in children)
            child_attempts = max(child.attempts for child in children)
            child_liability = max(child.liability for child in children)
            try:
                node_liability = Nanodollars(
                    node.liability_bound.value * node.limits.max_attempts
                )
                total_liability = node_liability + child_liability
            except ValueError as error:
                raise GraphValidationError(
                    f"liability bound overflows at node {node.node_id.value}"
                ) from error
            bound = _PathBound(
                transitions=1 + child_transitions,
                attempts=node.limits.max_attempts + child_attempts,
                liability=total_liability,
            )
        visiting.remove(node_id)
        memo[node_id] = bound
        return bound

    maximum = path_bound(definition.entry_node_id)
    unreachable = sorted(node_id.value for node_id in set(nodes) - visited)
    if unreachable:
        raise GraphValidationError(f"unreachable nodes: {unreachable}")
    for node in definition.nodes:
        bindings = (
            node.input_bindings
            if isinstance(node, OperationNode)
            else (() if node.answer_binding is None else (node.answer_binding,))
        )
        for binding in bindings:
            source_id = binding.source_node_id
            if source_id is None:
                continue
            source = nodes.get(source_id)
            if source is None:
                raise GraphValidationError(
                    f"node {node.node_id.value} binds missing artifact source {source_id.value}"
                )
            if not isinstance(source, OperationNode) or source.output is None:
                raise GraphValidationError(
                    f"node {node.node_id.value} binds source without declared output"
                )
            if source.output.role is not binding.role:
                raise GraphValidationError(
                    f"node {node.node_id.value} binds incompatible artifact role"
                )
            if source_id not in dominators[node.node_id]:
                raise GraphValidationError(
                    f"artifact source {source_id.value} does not dominate node {node.node_id.value}"
                )
    if maximum.transitions > definition.max_transitions:
        raise GraphValidationError(
            f"worst path needs {maximum.transitions} transitions, exceeding "
            f"declared maximum {definition.max_transitions}"
        )
    if maximum.attempts > definition.max_total_attempts:
        raise GraphValidationError(
            f"worst path needs {maximum.attempts} attempts, exceeding "
            f"declared maximum {definition.max_total_attempts}"
        )
    terminals = tuple(
        sorted(
            {node.status for node in definition.nodes if isinstance(node, TerminalNode)},
            key=lambda status: status.value,
        )
    )
    if not terminals:
        raise GraphValidationError("option has no terminal node")
    return ValidatedOption(
        definition=definition,
        max_path_transitions=maximum.transitions,
        max_path_attempts=maximum.attempts,
        max_path_liability=maximum.liability,
        terminal_statuses=terminals,
    )
