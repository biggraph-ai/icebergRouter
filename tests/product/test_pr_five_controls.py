"""PR 5 exact, terminating, and honestly named control-policy tests."""

from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.contracts import (  # noqa: E402
    OptionId, PolicyVersion, Probability, TaskFeatures,
)
from iceberg_router.policies import (  # noqa: E402
    DrawThenDeferMixturePolicy, FeasibleMixturePolicy, PolicyConfigurationError,
    RandomMixturePolicy, TaskFeatureRulePolicy, TaskRulePolicy, WorkloadRulePolicy,
)
from iceberg_router.policies.random_mixture import (  # noqa: E402
    _integer_distribution,
    _sample,
)
from tests.product.test_increment_six_policies import candidate, request  # noqa: E402


class ExactMixtureTests(unittest.TestCase):
    def test_trailing_zero_equivalent_probabilities_reduce_without_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            probabilities = {
                OptionId("a"): Probability(Decimal("0.2500000000000000000000000000")),
                OptionId("b"): Probability(Decimal("0.7500000000000000000000000000")),
            }
            self.assertEqual(
                _integer_distribution(probabilities),
                ((OptionId("a"), 1), (OptionId("b"), 3)),
            )
            policy = DrawThenDeferMixturePolicy(
                probabilities, PolicyVersion("draw-v1")
            )
            decision = policy.select(
                request(candidate("a"), candidate("b"), seed="exact-seed")
            )
        expected = probabilities[decision.selected_option_id]
        self.assertEqual(decision.selection_probability, expected)

    def test_unsupported_high_precision_rejects_before_sampling(self):
        tiny = Decimal("0." + "0" * 256 + "1")
        complement = Decimal("0." + "9" * 257)
        with self.assertRaisesRegex(PolicyConfigurationError, "256-bit sampler"):
            DrawThenDeferMixturePolicy(
                {
                    OptionId("tiny"): Probability(tiny),
                    OptionId("large"): Probability(complement),
                },
                PolicyVersion("draw-v1"),
            )

    def test_reduced_weights_define_every_integer_draw_threshold(self):
        distribution = ((OptionId("a"), 1), (OptionId("b"), 3))
        selected = []
        for draw in range(4):
            with patch(
                "iceberg_router.policies.random_mixture._uniform_index",
                return_value=draw,
            ):
                selected.append(_sample("ignored", distribution)[0])
        self.assertEqual(
            selected,
            [OptionId("a"), OptionId("b"), OptionId("b"), OptionId("b")],
        )

    def test_explicit_baseline_and_feasible_control_have_distinct_semantics(self):
        probabilities = {
            OptionId("small"): Probability(Decimal("0.75")),
            OptionId("large"): Probability(Decimal("0.25")),
        }
        baseline = DrawThenDeferMixturePolicy(
            probabilities, PolicyVersion("draw-v1")
        )
        feasible = FeasibleMixturePolicy(
            probabilities, PolicyVersion("feasible-v1")
        )
        candidates = (candidate("small"), candidate("large", False))
        deferred = next(
            baseline.select(request(*candidates, seed=f"seed-{index}"))
            for index in range(100)
            if baseline.select(
                request(*candidates, seed=f"seed-{index}")
            ).selected_option_id is None
        )
        selected = feasible.select(request(*candidates, seed="any-seed"))
        self.assertEqual(deferred.deferral_reason, "sampled_option_ineligible")
        self.assertEqual(deferred.selection_probability, Probability(Decimal("0.25")))
        self.assertEqual(selected.selected_option_id, OptionId("small"))
        self.assertEqual(selected.selection_probability, Probability(Decimal(1)))
        self.assertIs(RandomMixturePolicy, DrawThenDeferMixturePolicy)

    def test_deterministic_seed_replays_both_mechanisms(self):
        probabilities = {
            OptionId("small"): Probability(Decimal("0.6")),
            OptionId("large"): Probability(Decimal("0.4")),
        }
        source = request(candidate("small"), candidate("large"), seed="replay")
        for policy in (
            DrawThenDeferMixturePolicy(probabilities, PolicyVersion("draw-v1")),
            FeasibleMixturePolicy(probabilities, PolicyVersion("feasible-v1")),
        ):
            with self.subTest(policy=type(policy).__name__):
                self.assertEqual(policy.select(source), policy.select(source))


class InformativeRuleTests(unittest.TestCase):
    def test_task_features_route_arithmetic_and_document_tasks_differently(self):
        policy = TaskFeatureRulePolicy(
            {"arithmetic": OptionId("math"), "document": OptionId("retrieval")},
            PolicyVersion("task-features-v1"),
            "features-v1",
        )
        candidates = (candidate("math"), candidate("retrieval"))
        base = request(*candidates, workload="shared-workload")
        arithmetic = replace(
            base, task_features=TaskFeatures("arithmetic", ("short",), "features-v1")
        )
        document = replace(
            base, task_features=TaskFeatures("document", ("long",), "features-v1")
        )
        self.assertEqual(
            policy.select(arithmetic).selected_option_id, OptionId("math")
        )
        self.assertEqual(
            policy.select(document).selected_option_id, OptionId("retrieval")
        )

    def test_workload_policy_has_reviewed_compatibility_alias(self):
        self.assertIs(TaskRulePolicy, WorkloadRulePolicy)

    def test_configuration_snapshot_is_immutable_and_versioned(self):
        source = request(candidate("small"))
        with self.assertRaises(TypeError):
            source.configuration_snapshot.options[OptionId("other")] = next(
                iter(source.configuration_snapshot.options.values())
            )
        changed = replace(
            source.configuration_snapshot, version="config-v2"
        )
        self.assertNotEqual(changed, source.configuration_snapshot)


if __name__ == "__main__":
    unittest.main()
