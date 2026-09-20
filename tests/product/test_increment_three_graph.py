import json
from pathlib import Path
import sys
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AccountId,
    ApplicabilityRule,
    ApplicabilityVersion,
    ArtifactDeclaration,
    ArtifactRole,
    BoundedContractEvidence,
    BoundVersion,
    Branch,
    BranchOutcome,
    EstimatorVersion,
    InputBinding,
    MAX_NANODOLLARS,
    Nanodollars,
    NodeId,
    OperationKind,
    OperationLimits,
    OperationNode,
    OptionDefinition,
    OptionId,
    OptionVersion,
    ResourceIdentity,
    TerminalNode,
    TerminalStatus,
)
from iceberg_router.core import GraphValidationError, validate_option  # noqa: E402


def limits(max_attempts: int = 1) -> OperationLimits:
    return OperationLimits(
        max_attempts=max_attempts,
        timeout_ms=1_000,
        max_input_tokens=100,
        max_output_tokens=50,
    )


def resource(kind: OperationKind) -> ResourceIdentity:
    return ResourceIdentity("fixture", kind.value, "v1", "prompt-v1")


def evidence(bound: int) -> BoundedContractEvidence:
    return BoundedContractEvidence(
        "evidence-v1", "tariff-v1", "bound-v1", Nanodollars(bound), True, True, True
    )


def branches(**outcomes: str) -> tuple[Branch, ...]:
    return tuple(
        Branch(BranchOutcome(outcome), NodeId(target)) for outcome, target in outcomes.items()
    )


def model_node(
    name: str,
    *,
    success: str,
    error: str,
    unknown: str,
    unfunded: str = "defer",
    liability: int,
    max_attempts: int = 1,
    inputs: tuple[InputBinding, ...] | None = None,
) -> OperationNode:
    return OperationNode(
        node_id=NodeId(name),
        kind=OperationKind.MODEL_CALL,
        account_id=AccountId("model-serving"),
        liability_bound=Nanodollars(liability),
        limits=limits(max_attempts),
        operation_version="model-profile-v1",
        branches=branches(
            success=success, error=error, unknown=unknown, unfunded=unfunded
        ),
        input_bindings=inputs
        if inputs is not None
        else (InputBinding("request", None, ArtifactRole.ORIGINAL_REQUEST),),
        output=ArtifactDeclaration(ArtifactRole.CANDIDATE_ANSWER, "candidate-v1"),
        resource=resource(OperationKind.MODEL_CALL),
        bounded_contract=evidence(liability),
    )


def option(nodes: tuple, *, max_transitions: int = 3, max_attempts: int = 4) -> OptionDefinition:
    return OptionDefinition(
        option_id=OptionId("cheap-check-repair"),
        version=OptionVersion("option-v1"),
        entry_node_id=NodeId("draft"),
        applicability=ApplicabilityRule(
            "standard-request", ApplicabilityVersion("applicability-v1")
        ),
        expected_cost_estimator_version=EstimatorVersion("expected-v1"),
        bound_calculator_version=BoundVersion("bound-v1"),
        max_transitions=max_transitions,
        max_total_attempts=max_attempts,
        nodes=nodes,
    )


def valid_option() -> OptionDefinition:
    draft = model_node(
        "draft", success="verify", error="defer", unknown="defer", liability=10
    )
    verify = OperationNode(
        node_id=NodeId("verify"),
        kind=OperationKind.VERIFY,
        account_id=AccountId("verification"),
        liability_bound=Nanodollars(3),
        limits=limits(),
        operation_version="checker-v1",
        branches=(
            Branch(BranchOutcome.PASS, NodeId("complete-draft")),
            Branch(BranchOutcome.FAIL, NodeId("repair")),
            Branch(BranchOutcome.UNKNOWN, NodeId("defer")),
            Branch(BranchOutcome.ERROR, NodeId("defer")),
            Branch(BranchOutcome.UNFUNDED, NodeId("defer")),
        ),
        input_bindings=(
            InputBinding("candidate", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),
        ),
        output=ArtifactDeclaration(ArtifactRole.CHECKER_EVIDENCE, "checker-v1"),
        resource=resource(OperationKind.VERIFY),
        bounded_contract=evidence(3),
    )
    repair = model_node(
        "repair",
        success="complete",
        error="failed",
        unknown="failed",
        liability=20,
        max_attempts=2,
        inputs=(
            InputBinding("candidate", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),
            InputBinding("checker", NodeId("verify"), ArtifactRole.CHECKER_EVIDENCE),
        ),
    )
    return option(
        (
            draft,
            verify,
            repair,
            TerminalNode(
                NodeId("complete-draft"), TerminalStatus.COMPLETE, "verified_answer",
                InputBinding("answer", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),
            ),
            TerminalNode(
                NodeId("complete"), TerminalStatus.COMPLETE, "repaired_answer",
                InputBinding("answer", NodeId("repair"), ArtifactRole.CANDIDATE_ANSWER),
            ),
            TerminalNode(NodeId("defer"), TerminalStatus.DEFERRED, "verification_unknown", None),
            TerminalNode(NodeId("failed"), TerminalStatus.FAILED, "repair_failed", None),
        )
    )


class OptionContractTests(unittest.TestCase):
    def test_option_round_trips_as_strict_portable_json(self):
        definition = valid_option()
        wire = definition.to_json()
        json.dumps(wire)
        self.assertEqual(definition, OptionDefinition.from_json(wire))
        self.assertEqual("1", wire["schemaVersion"])
        self.assertEqual("candidate_answer", wire["nodes"][0]["output"]["role"])
        self.assertEqual("original_request", wire["nodes"][0]["inputBindings"][0]["role"])
        self.assertEqual("10", wire["nodes"][0]["liabilityBoundNanos"])

    def test_limits_reject_bool_zero_attempts_and_negative_tokens(self):
        for kwargs in (
            dict(max_attempts=True, timeout_ms=1, max_input_tokens=0, max_output_tokens=0),
            dict(max_attempts=0, timeout_ms=1, max_input_tokens=0, max_output_tokens=0),
            dict(max_attempts=1, timeout_ms=0, max_input_tokens=0, max_output_tokens=0),
            dict(max_attempts=1, timeout_ms=1, max_input_tokens=-1, max_output_tokens=0),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises((TypeError, ValueError)):
                    OperationLimits(**kwargs)

    def test_duplicate_branch_outcome_is_rejected_by_contract(self):
        with self.assertRaises(ValueError):
            OperationNode(
                NodeId("duplicate"),
                OperationKind.MODEL_CALL,
                AccountId("model-serving"),
                Nanodollars(1),
                limits(),
                "model-v1",
                (
                    Branch(BranchOutcome.SUCCESS, NodeId("a")),
                    Branch(BranchOutcome.SUCCESS, NodeId("b")),
                ),
                (),
                None,
                resource(OperationKind.MODEL_CALL),
                evidence(1),
            )


class GraphValidationTests(unittest.TestCase):
    def test_valid_conditional_graph_calculates_worst_path(self):
        validated = validate_option(valid_option())
        self.assertEqual(3, validated.max_path_transitions)
        self.assertEqual(4, validated.max_path_attempts)
        self.assertEqual(Nanodollars(53), validated.max_path_liability)
        self.assertEqual(
            (TerminalStatus.COMPLETE, TerminalStatus.DEFERRED, TerminalStatus.FAILED),
            validated.terminal_statuses,
        )

    def test_missing_required_unknown_branch_is_rejected(self):
        definition = valid_option()
        draft = definition.nodes[0]
        assert isinstance(draft, OperationNode)
        incomplete = OperationNode(
            draft.node_id,
            draft.kind,
            draft.account_id,
            draft.liability_bound,
            draft.limits,
            draft.operation_version,
            tuple(branch for branch in draft.branches if branch.outcome is not BranchOutcome.UNKNOWN),
            draft.input_bindings,
            draft.output,
            draft.resource,
            draft.bounded_contract,
        )
        with self.assertRaisesRegex(GraphValidationError, "missing outcomes"):
            validate_option(option((incomplete, *definition.nodes[1:])))

    def test_dangling_target_is_rejected(self):
        definition = valid_option()
        draft = definition.nodes[0]
        assert isinstance(draft, OperationNode)
        dangling = model_node(
            "draft", success="missing", error="defer", unknown="defer", liability=10
        )
        with self.assertRaisesRegex(GraphValidationError, "targets missing node"):
            validate_option(option((dangling, *definition.nodes[1:])))

    def test_duplicate_and_unreachable_nodes_are_rejected(self):
        definition = valid_option()
        with self.assertRaisesRegex(GraphValidationError, "duplicate node ID"):
            validate_option(option((*definition.nodes, definition.nodes[-1])))
        unreachable = TerminalNode(NodeId("orphan"), TerminalStatus.FAILED, "orphan", None)
        with self.assertRaisesRegex(GraphValidationError, "unreachable nodes"):
            validate_option(option((*definition.nodes, unreachable)))

    def test_cycles_are_rejected_in_increment_three(self):
        definition = valid_option()
        repair = model_node(
            "repair", success="verify", error="failed", unknown="failed", liability=20
        )
        nodes = tuple(repair if node.node_id == NodeId("repair") else node for node in definition.nodes)
        with self.assertRaisesRegex(GraphValidationError, "cycle detected"):
            validate_option(option(nodes))

    def test_declared_transition_and_attempt_limits_are_enforced(self):
        definition = valid_option()
        with self.assertRaisesRegex(GraphValidationError, "transitions"):
            validate_option(option(definition.nodes, max_transitions=2))
        with self.assertRaisesRegex(GraphValidationError, "attempts"):
            validate_option(option(definition.nodes, max_attempts=3))

    def test_liability_overflow_is_rejected(self):
        huge = model_node(
            "draft",
            success="complete",
            error="complete",
            unknown="complete",
            unfunded="complete",
            liability=MAX_NANODOLLARS,
            max_attempts=2,
        )
        complete = TerminalNode(
            NodeId("complete"), TerminalStatus.COMPLETE, "done",
            InputBinding("answer", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),
        )
        definition = option((huge, complete), max_transitions=1, max_attempts=2)
        with self.assertRaisesRegex(GraphValidationError, "overflows"):
            validate_option(definition)

    def test_terminal_only_option_has_zero_liability(self):
        terminal = TerminalNode(NodeId("draft"), TerminalStatus.DEFERRED, "not_applicable", None)
        validated = validate_option(option((terminal,), max_transitions=0, max_attempts=0))
        self.assertEqual(Nanodollars(0), validated.max_path_liability)
        self.assertEqual(0, validated.max_path_attempts)


if __name__ == "__main__":
    unittest.main()
