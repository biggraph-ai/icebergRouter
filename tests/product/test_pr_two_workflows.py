"""PR 2 executable data-flow workflow acceptance tests."""

from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    AccountId, ApplicabilityRule, ApplicabilityVersion, ArtifactDeclaration,
    ArtifactRole, BoundedContractEvidence, BoundVersion, Branch, BranchOutcome, BudgetId, DecisionId,
    EstimatorVersion, InputBinding, Nanodollars, NodeId, OperationKind,
    OperationLimits, OperationNode, OperationResult, OptionDefinition, OptionId,
    OptionVersion, RequestId, ResourceIdentity, TerminalNode, TerminalStatus, UsageState,
)
from iceberg_router.core import (  # noqa: E402
    ArtifactResolutionError, BudgetGovernor, ExecutionRequest, GraphValidationError,
    OptionExecutor, SQLiteBudgetLedger, validate_option,
)
from iceberg_router.testing import (  # noqa: E402
    DeterministicIdentityFactory, FixedClock, ScriptedAdapter,
)


def branches(kind: OperationKind, success: str, failure: str) -> tuple[Branch, ...]:
    outcomes = {
        OperationKind.MODEL_CALL: (
            BranchOutcome.SUCCESS, BranchOutcome.ERROR, BranchOutcome.UNKNOWN,
            BranchOutcome.UNFUNDED,
        ),
        OperationKind.VERIFY: (
            BranchOutcome.PASS, BranchOutcome.FAIL, BranchOutcome.UNKNOWN,
            BranchOutcome.ERROR, BranchOutcome.UNFUNDED,
        ),
        OperationKind.DETERMINISTIC_TOOL: (
            BranchOutcome.SUCCESS, BranchOutcome.ERROR, BranchOutcome.UNKNOWN,
            BranchOutcome.INAPPLICABLE, BranchOutcome.UNFUNDED,
        ),
    }[kind]
    return tuple(
        Branch(outcome, NodeId(success if outcome in (BranchOutcome.SUCCESS, BranchOutcome.PASS) else failure))
        for outcome in outcomes
    )


def operation(name, kind, success, failure, inputs, role) -> OperationNode:
    resource = ResourceIdentity(
        "fixture", kind.value, "v1", "prompt-v1",
        "checker-v1" if kind is OperationKind.VERIFY else None,
    )
    return OperationNode(
        NodeId(name), kind, AccountId("workflow"), Nanodollars(5),
        OperationLimits(1, 1000, 100, 50), f"{name}-v1",
        branches(kind, success, failure), inputs,
        ArtifactDeclaration(role, f"{role.value}-v1"),
        resource,
        BoundedContractEvidence(
            "evidence-v1", "tariff-v1", "bound-v1", Nanodollars(5), True, True, True
        ),
    )


def workflow_option():
    draft = operation(
        "draft", OperationKind.MODEL_CALL, "check", "defer",
        (InputBinding("request", None, ArtifactRole.ORIGINAL_REQUEST),),
        ArtifactRole.CANDIDATE_ANSWER,
    )
    check = operation(
        "check", OperationKind.VERIFY, "complete-draft", "repair",
        (InputBinding("candidate", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),),
        ArtifactRole.CHECKER_EVIDENCE,
    )
    repair = operation(
        "repair", OperationKind.MODEL_CALL, "complete-repair", "defer",
        (
            InputBinding("candidate", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),
            InputBinding("checker", NodeId("check"), ArtifactRole.CHECKER_EVIDENCE),
        ),
        ArtifactRole.CANDIDATE_ANSWER,
    )
    terminals = (
        TerminalNode(
            NodeId("complete-draft"), TerminalStatus.COMPLETE, "verified",
            InputBinding("answer", NodeId("draft"), ArtifactRole.CANDIDATE_ANSWER),
        ),
        TerminalNode(
            NodeId("complete-repair"), TerminalStatus.COMPLETE, "repaired",
            InputBinding("answer", NodeId("repair"), ArtifactRole.CANDIDATE_ANSWER),
        ),
        TerminalNode(NodeId("defer"), TerminalStatus.DEFERRED, "unresolved", None),
    )
    return validate_option(OptionDefinition(
        OptionId("workflow"), OptionVersion("option-v1"), NodeId("draft"),
        ApplicabilityRule("always", ApplicabilityVersion("applicability-v1")),
        EstimatorVersion("estimate-v1"), BoundVersion("bound-v1"), 3, 3,
        (draft, check, repair, *terminals),
    ))


class WorkflowTests(unittest.TestCase):
    def execute(self, option, adapters):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        ledger = SQLiteBudgetLedger(Path(temporary.name) / "ledger.sqlite3")
        budget = BudgetId("budget-1")
        ledger.create_budget(budget, Nanodollars(100))
        executor = OptionExecutor(
            BudgetGovernor(ledger), adapters,
            identity_factory=DeterministicIdentityFactory(), clock=FixedClock(),
        )
        request = ExecutionRequest(
            RequestId("request-1"), DecisionId("decision-1"), budget, option, True,
            {"prompt": "protected request"},
        )
        return executor.execute(request), ledger, budget

    def test_draft_check_repair_receives_exact_predecessor_references(self):
        model = ScriptedAdapter((
            OperationResult(BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(2), "draft-ref"),
            OperationResult(BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(3), "repair-ref"),
        ))
        checker = ScriptedAdapter((
            OperationResult(BranchOutcome.FAIL, UsageState.KNOWN, Nanodollars(1), "checker-ref"),
        ))
        result, _, _ = self.execute(
            workflow_option(),
            {
                workflow_option().definition.nodes[0].resource: model,
                workflow_option().definition.nodes[1].resource: checker,
            },
        )
        self.assertEqual(model.calls[0].inputs["request"].role, ArtifactRole.ORIGINAL_REQUEST)
        self.assertEqual(checker.calls[0].inputs["candidate"].reference, "draft-ref")
        self.assertEqual(model.calls[1].inputs["candidate"].reference, "draft-ref")
        self.assertEqual(model.calls[1].inputs["checker"].reference, "checker-ref")
        self.assertEqual(result.output_reference, "repair-ref")
        self.assertNotEqual(result.output_reference, "checker-ref")

    def test_missing_artifact_fails_before_next_authorization(self):
        model = ScriptedAdapter((
            OperationResult(BranchOutcome.SUCCESS, UsageState.KNOWN, Nanodollars(2), None),
        ))
        checker = ScriptedAdapter(())
        with self.assertRaises(ArtifactResolutionError):
            self.execute(
                workflow_option(),
                {
                    workflow_option().definition.nodes[0].resource: model,
                    workflow_option().definition.nodes[1].resource: checker,
                },
            )
        self.assertEqual(checker.calls, [])

    def test_tool_timeout_and_exception_use_typed_unknown_branch_and_keep_hold(self):
        tool = operation(
            "tool", OperationKind.DETERMINISTIC_TOOL, "done", "defer",
            (InputBinding("request", None, ArtifactRole.ORIGINAL_REQUEST),),
            ArtifactRole.DIAGNOSTIC,
        )
        option = validate_option(OptionDefinition(
            OptionId("tool"), OptionVersion("v1"), NodeId("tool"),
            ApplicabilityRule("always", ApplicabilityVersion("v1")),
            EstimatorVersion("v1"), BoundVersion("v1"), 1, 1,
            (
                tool,
                TerminalNode(NodeId("done"), TerminalStatus.DEFERRED, "diagnostic", None),
                TerminalNode(NodeId("defer"), TerminalStatus.DEFERRED, "tool_unknown", None),
            ),
        ))
        for error in (TimeoutError("offline timeout"), RuntimeError("tool failed")):
            with self.subTest(error=type(error).__name__):
                adapter = ScriptedAdapter((error,))
                result, ledger, budget = self.execute(
            option, {tool.resource: adapter}
                )
                self.assertEqual(result.status, TerminalStatus.DEFERRED)
                self.assertEqual(result.attempts[0].result.outcome, BranchOutcome.UNKNOWN)
                self.assertEqual(result.attempts[0].result.usage_state, UsageState.UNKNOWN)
                self.assertEqual(
                    ledger.snapshot(budget).outstanding_liability, Nanodollars(5)
                )

    def test_incompatible_artifact_role_is_rejected_statically(self):
        definition = workflow_option().definition
        check = definition.nodes[1]
        assert isinstance(check, OperationNode)
        incompatible = OperationNode(
            check.node_id, check.kind, check.account_id, check.liability_bound,
            check.limits, check.operation_version, check.branches,
            (InputBinding("candidate", NodeId("draft"), ArtifactRole.CHECKER_EVIDENCE),),
            check.output,
            check.resource,
            check.bounded_contract,
        )
        with self.assertRaisesRegex(GraphValidationError, "incompatible artifact role"):
            validate_option(OptionDefinition(
                definition.option_id, definition.version, definition.entry_node_id,
                definition.applicability, definition.expected_cost_estimator_version,
                definition.bound_calculator_version, definition.max_transitions,
                definition.max_total_attempts,
                (definition.nodes[0], incompatible, *definition.nodes[2:]),
            ))


if __name__ == "__main__":
    unittest.main()
