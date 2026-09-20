from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.adapters import SingleAttemptAdapter  # noqa: E402
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
    BudgetId,
    CandidateDecision,
    CostEstimate,
    DecisionId,
    EstimateState,
    EstimatorVersion,
    InputBinding,
    Nanodollars,
    NodeId,
    OperationKind,
    OperationLimits,
    OperationNode,
    OperationResult,
    OptionDefinition,
    OptionId,
    OptionVersion,
    PolicyRequest,
    PolicyVersion,
    Probability,
    RequestId,
    ResourceIdentity,
    SnapshotVersion,
    TerminalNode,
    TerminalStatus,
    UsageState,
    WorkloadId,
)
from iceberg_router.core import (  # noqa: E402
    BudgetGovernor,
    IcebergRouter,
    PolicyContractError,
    RouteRequest,
    RoutingConfigurationError,
    SQLiteAuditJournal,
    SQLiteBudgetLedger,
    OptionExecutor,
    validate_option,
)
from iceberg_router.policies import FixedPolicy  # noqa: E402
from iceberg_router.testing import DeterministicIdentityFactory, FixedClock  # noqa: E402


NOW = "2026-09-16T12:00:00Z"
MODEL_RESOURCE = ResourceIdentity("fixture", "small-model", "v1", "prompt-v1")


def validated_option(option_id: str = "small"):
    terminal = NodeId("complete")
    operation = OperationNode(
        NodeId("start"),
        OperationKind.MODEL_CALL,
        AccountId("model-serving"),
        Nanodollars(10),
        OperationLimits(1, 1_000, 100, 50),
        "operation-v1",
        (
            Branch(BranchOutcome.SUCCESS, terminal),
            Branch(BranchOutcome.ERROR, terminal),
            Branch(BranchOutcome.UNKNOWN, terminal),
            Branch(BranchOutcome.UNFUNDED, terminal),
        ),
        (InputBinding("request", None, ArtifactRole.ORIGINAL_REQUEST),),
        ArtifactDeclaration(ArtifactRole.CANDIDATE_ANSWER, "candidate-v1"),
        MODEL_RESOURCE,
        BoundedContractEvidence(
            "evidence-v1", "tariff-v1", "bound-v1", Nanodollars(10), True, True, True
        ),
    )
    return validate_option(
        OptionDefinition(
            OptionId(option_id),
            OptionVersion("option-v1"),
            operation.node_id,
            ApplicabilityRule("always", ApplicabilityVersion("applicability-v1")),
            EstimatorVersion("estimate-v1"),
            BoundVersion("bound-v1"),
            1,
            1,
            (
                operation,
                TerminalNode(
                    terminal,
                    TerminalStatus.COMPLETE,
                    "complete",
                    InputBinding(
                        "answer", operation.node_id, ArtifactRole.CANDIDATE_ANSWER
                    ),
                ),
            ),
        )
    )


def candidate(option_id: str = "small", *, eligible: bool = True, bound: int = 10):
    return CandidateDecision(
        OptionId(option_id),
        eligible,
        ("eligible" if eligible else "blocked",),
        None,
        CostEstimate(EstimateState.KNOWN, "estimate-v1", Nanodollars(5)),
        CostEstimate(EstimateState.KNOWN, "bound-v1", Nanodollars(bound)),
    )


def policy_request(*candidates):
    return PolicyRequest(
        DecisionId("decision-1"),
        RequestId("request-1"),
        WorkloadId("chat"),
        SnapshotVersion("snapshot-v1"),
        tuple(candidates),
        "seed-1",
    )


class RouterTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.ledger = SQLiteBudgetLedger(root / "ledger.sqlite3")
        self.journal = SQLiteAuditJournal(root / "journal.sqlite3")
        self.budget_id = BudgetId("budget-1")
        self.ledger.create_budget(self.budget_id, Nanodollars(100))
        self.identities = DeterministicIdentityFactory()
        self.clock = FixedClock(NOW)
        transport = lambda context: OperationResult(
            BranchOutcome.SUCCESS,
            UsageState.KNOWN,
            Nanodollars(7),
            "output-1",
            "receipt-1",
        )
        adapter = SingleAttemptAdapter(
            OperationKind.MODEL_CALL, "operation-v1", MODEL_RESOURCE, transport
        )
        self.executor = OptionExecutor(
            BudgetGovernor(self.ledger),
            {MODEL_RESOURCE: adapter},
            identity_factory=self.identities,
            clock=self.clock,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def router(self, policy):
        return IcebergRouter(
            policy,
            self.executor,
            self.journal,
            identity_factory=self.identities,
            clock=self.clock,
        )

    def test_selected_option_is_audited_executed_and_settled(self):
        option = validated_option()
        request = RouteRequest(
            policy_request(candidate()), self.budget_id, {OptionId("small"): option},
            {"prompt": "offline"},
        )
        result = self.router(
            FixedPolicy(OptionId("small"), PolicyVersion("fixed-v1"))
        ).route(request)
        self.assertEqual(result.decision.selected_option_id, OptionId("small"))
        self.assertEqual(result.execution.output_reference, "output-1")
        snapshot = self.ledger.snapshot(self.budget_id)
        self.assertEqual(snapshot.confirmed_spend, Nanodollars(7))
        self.assertEqual(snapshot.outstanding_liability, Nanodollars(0))
        entries = self.journal.entries()
        self.assertEqual(entries[0].event_type.value, "decision")
        self.assertEqual(entries[-1].event_type.value, "execution")
        self.assertGreater(len(entries), 2)
        self.assertEqual(self.journal.verify_chain(), len(entries))

    def test_policy_deferral_is_audited_without_spend(self):
        option = validated_option()
        result = self.router(
            FixedPolicy(OptionId("missing"), PolicyVersion("fixed-v1"))
        ).route(
            RouteRequest(
                policy_request(candidate()),
                self.budget_id,
                {OptionId("small"): option},
            )
        )
        self.assertIsNone(result.execution)
        self.assertEqual(result.decision.deferral_reason, "fixed_option_missing")
        self.assertEqual(self.ledger.snapshot(self.budget_id).confirmed_spend, Nanodollars(0))
        self.assertEqual(len(self.journal.entries()), 1)

    def test_duplicate_decision_returns_recorded_completion(self):
        option = validated_option()
        route_request = RouteRequest(
            policy_request(candidate()),
            self.budget_id,
            {OptionId("small"): option},
        )
        router = self.router(
            FixedPolicy(OptionId("small"), PolicyVersion("fixed-v1"))
        )
        first = router.route(route_request)
        replay = router.route(route_request)
        self.assertEqual(replay, first)
        self.assertEqual(
            self.ledger.snapshot(self.budget_id).confirmed_spend, Nanodollars(7)
        )

    def test_candidate_and_executable_option_sets_must_match(self):
        with self.assertRaises(RoutingConfigurationError):
            RouteRequest(policy_request(candidate()), self.budget_id, {})

    def test_eligible_candidate_bound_cannot_understate_graph_bound(self):
        with self.assertRaises(RoutingConfigurationError):
            RouteRequest(
                policy_request(candidate(bound=9)),
                self.budget_id,
                {OptionId("small"): validated_option()},
            )

    def test_route_request_copies_option_mapping(self):
        options = {OptionId("small"): validated_option()}
        request = RouteRequest(policy_request(candidate()), self.budget_id, options)
        options.clear()
        self.assertIn(OptionId("small"), request.options)
        with self.assertRaises(TypeError):
            request.options[OptionId("other")] = validated_option("other")

    def test_policy_cannot_change_immutable_snapshot_fields(self):
        fixed = FixedPolicy(OptionId("small"), PolicyVersion("fixed-v1"))

        class CorruptingPolicy:
            policy_version = fixed.policy_version

            def select(self, request):
                decision = fixed.select(request)
                return type(decision)(
                    DecisionId("different-decision"),
                    decision.request_id,
                    decision.workload_id,
                    decision.policy_version,
                    decision.snapshot_version,
                    decision.candidates,
                    decision.selected_option_id,
                    Probability(Decimal(1)),
                    decision.randomization_seed,
                )

        route_request = RouteRequest(
            policy_request(candidate()),
            self.budget_id,
            {OptionId("small"): validated_option()},
        )
        with self.assertRaises(PolicyContractError):
            self.router(CorruptingPolicy()).route(route_request)
        self.assertEqual(self.journal.entries(), ())


if __name__ == "__main__":
    unittest.main()
