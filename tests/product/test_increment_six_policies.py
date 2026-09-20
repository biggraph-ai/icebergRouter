from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
import sys
import unittest


BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    CandidateDecision,
    ConfigurationSnapshot,
    CostEstimate,
    DecisionId,
    EstimateState,
    FrozenOptionVersion,
    Nanodollars,
    OptionId,
    PolicyVersion,
    Probability,
    RequestId,
    SnapshotVersion,
    TaskFeatures,
    WorkloadId,
)
from iceberg_router.policies import (  # noqa: E402
    FixedPolicy,
    DrawThenDeferMixturePolicy,
    FeasibleMixturePolicy,
    PolicyConfigurationError,
    PolicyRequest,
    RandomMixturePolicy,
    TaskRulePolicy,
    TaskFeatureRulePolicy,
    WorkloadRulePolicy,
)


def candidate(name: str, eligible: bool = True) -> CandidateDecision:
    return CandidateDecision(
        OptionId(name),
        eligible,
        ("eligible" if eligible else "unsupported",),
        None,
        CostEstimate(EstimateState.KNOWN, "estimate-v1", Nanodollars(5)),
        CostEstimate(EstimateState.KNOWN, "bound-v1", Nanodollars(10)),
    )


def request(*items: CandidateDecision, workload: str = "chat", seed: str = "seed-1"):
    configuration = ConfigurationSnapshot(
        "config-v1",
        {
            item.option_id: FrozenOptionVersion(
                "option-v1", f"{item.option_id.value}-model-v1", "prompt-v1", "checker-v1"
            )
            for item in items
        },
    )
    return PolicyRequest(
        DecisionId("decision-1"),
        RequestId("request-1"),
        WorkloadId(workload),
        SnapshotVersion("snapshot-v1"),
        tuple(items),
        seed,
        TaskFeatures("general", (), "features-v1"),
        configuration,
    )


class PolicyRequestTests(unittest.TestCase):
    def test_request_rejects_empty_and_duplicate_candidates(self):
        with self.assertRaises(ValueError):
            request()
        with self.assertRaises(ValueError):
            request(candidate("small"), candidate("small"))


class FixedPolicyTests(unittest.TestCase):
    def test_selects_configured_eligible_option_and_preserves_candidates(self):
        policy = FixedPolicy(OptionId("small"), PolicyVersion("fixed-v1"))
        source = request(candidate("small"), candidate("large", False))
        decision = policy.select(source)
        self.assertEqual(decision.selected_option_id, OptionId("small"))
        self.assertEqual(decision.selection_probability, Probability(Decimal(1)))
        self.assertEqual(decision.candidates, source.candidates)
        self.assertEqual(decision.policy_version, PolicyVersion("fixed-v1"))

    def test_missing_or_ineligible_fixed_option_defers_explicitly(self):
        policy = FixedPolicy(OptionId("large"), PolicyVersion("fixed-v1"))
        missing = policy.select(request(candidate("small")))
        blocked = policy.select(request(candidate("small"), candidate("large", False)))
        self.assertEqual(missing.deferral_reason, "fixed_option_missing")
        self.assertEqual(blocked.deferral_reason, "fixed_option_ineligible")
        self.assertEqual(blocked.selection_probability.to_json(), "1")


class TaskRulePolicyTests(unittest.TestCase):
    def test_workload_rule_and_fallback_are_deterministic(self):
        policy = TaskRulePolicy(
            {WorkloadId("code"): OptionId("large")},
            PolicyVersion("task-v1"),
            OptionId("small"),
        )
        candidates = (candidate("small"), candidate("large"))
        self.assertEqual(
            policy.select(request(*candidates, workload="code")).selected_option_id,
            OptionId("large"),
        )
        self.assertEqual(
            policy.select(request(*candidates, workload="chat")).selected_option_id,
            OptionId("small"),
        )

    def test_no_rule_and_ineligible_rule_defer(self):
        no_fallback = TaskRulePolicy(
            {WorkloadId("code"): OptionId("large")}, PolicyVersion("task-v1")
        )
        self.assertEqual(
            no_fallback.select(request(candidate("small"))).deferral_reason,
            "no_workload_rule",
        )
        self.assertEqual(
            no_fallback.select(
                request(candidate("large", False), workload="code")
            ).deferral_reason,
            "rule_option_ineligible",
        )

    def test_rule_mapping_is_copied_and_immutable(self):
        rules = {WorkloadId("code"): OptionId("large")}
        policy = TaskRulePolicy(rules, PolicyVersion("task-v1"))
        rules[WorkloadId("chat")] = OptionId("small")
        self.assertNotIn(WorkloadId("chat"), policy.rules)
        with self.assertRaises(TypeError):
            policy.rules[WorkloadId("chat")] = OptionId("small")
        with self.assertRaises(FrozenInstanceError):
            policy.policy_version = PolicyVersion("changed")


class RandomMixturePolicyTests(unittest.TestCase):
    def policy(self):
        return RandomMixturePolicy(
            {
                OptionId("large"): Probability(Decimal("0.25")),
                OptionId("small"): Probability(Decimal("0.75")),
            },
            PolicyVersion("mixture-v1"),
        )

    def test_same_seed_replays_same_selection_and_probability(self):
        policy = self.policy()
        source = request(candidate("small"), candidate("large"), seed="replay-seed")
        first = policy.select(source)
        second = policy.select(source)
        self.assertEqual(first, second)
        self.assertEqual(
            first.selection_probability,
            policy.probabilities[first.selected_option_id],
        )

    def test_different_seeds_cover_configured_assignments(self):
        policy = self.policy()
        selected = {
            policy.select(
                request(candidate("small"), candidate("large"), seed=f"seed-{index}")
            ).selected_option_id
            for index in range(100)
        }
        self.assertEqual(selected, {OptionId("small"), OptionId("large")})

    def test_ineligible_draw_defers_with_aggregate_deferral_probability(self):
        policy = self.policy()
        source_candidates = (candidate("small"), candidate("large", False))
        decisions = [
            policy.select(request(*source_candidates, seed=f"seed-{index}"))
            for index in range(100)
        ]
        deferred = next(item for item in decisions if item.selected_option_id is None)
        self.assertEqual(deferred.deferral_reason, "sampled_option_ineligible")
        self.assertEqual(deferred.selection_probability.to_json(), "0.25")

    def test_configuration_requires_positive_probabilities_summing_to_one(self):
        with self.assertRaises(PolicyConfigurationError):
            RandomMixturePolicy(
                {OptionId("small"): Probability(Decimal("0.8"))},
                PolicyVersion("mixture-v1"),
            )
        with self.assertRaises(PolicyConfigurationError):
            RandomMixturePolicy(
                {
                    OptionId("small"): Probability(Decimal(1) - Decimal("1e-257")),
                    OptionId("large"): Probability(Decimal("1e-257")),
                },
                PolicyVersion("mixture-v1"),
            )
        with self.assertRaises(PolicyConfigurationError):
            RandomMixturePolicy(
                {
                    OptionId("small"): Probability(Decimal(1)),
                    OptionId("large"): Probability(Decimal(0)),
                },
                PolicyVersion("mixture-v1"),
            )

    def test_all_configured_options_must_exist_in_snapshot(self):
        with self.assertRaises(PolicyConfigurationError):
            self.policy().select(request(candidate("small")))

    def test_probability_mapping_is_copied_and_immutable(self):
        probabilities = {OptionId("small"): Probability(Decimal(1))}
        policy = RandomMixturePolicy(probabilities, PolicyVersion("mixture-v1"))
        probabilities[OptionId("large")] = Probability(Decimal("0.5"))
        self.assertNotIn(OptionId("large"), policy.probabilities)
        with self.assertRaises(TypeError):
            policy.probabilities[OptionId("large")] = Probability(Decimal("0.5"))


if __name__ == "__main__":
    unittest.main()
