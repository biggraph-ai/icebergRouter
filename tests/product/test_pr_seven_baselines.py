"""PR 7 reproducible synthetic baseline experiment acceptance tests."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src"))

from iceberg_router.experiments.baseline import (  # noqa: E402
    DEFAULT_FIXTURE, DEFAULT_OPTIONS, STRATEGIES, ExperimentConfigurationError,
    _choice, run_baselines,
)


class BaselineExperimentTests(unittest.TestCase):
    def test_frozen_portfolio_and_splits_cover_declared_design(self):
        portfolio = json.loads(DEFAULT_OPTIONS.read_text())
        workload = json.loads(DEFAULT_FIXTURE.read_text())
        self.assertEqual(len(portfolio["options"]), 6)
        self.assertEqual({row["taskFamily"] for row in workload["requests"]},
                         {"arithmetic", "document", "classification"})
        self.assertEqual({row["split"] for row in workload["requests"]},
                         {"train", "calibration", "probe", "final_evaluation"})
        kinds = {item["kind"] for item in portfolio["options"]}
        self.assertIn("deterministic", kinds)
        self.assertIn("single-model", kinds)
        self.assertIn("draft-check-repair", kinds)

    def test_all_separately_named_controls_use_shared_contract(self):
        report = run_baselines()
        self.assertEqual(tuple(report["strategies"]), STRATEGIES)
        self.assertEqual(report["evidence"], "synthetic-mechanics-only")
        self.assertFalse(any(report["claims"].values()))
        denominators = {
            item["coverage"]["denominator"] for item in report["strategies"].values()
        }
        self.assertEqual(denominators, {6})
        for item in report["strategies"].values():
            self.assertIn("pairedUtilityDifferenceVsFixed95PercentInterval", item)
            self.assertIn("servedTaskQuality", item)
            self.assertIn("unresolvedHoldsNanos", item)

    def test_final_counterfactual_labels_do_not_affect_selection(self):
        workload = json.loads(DEFAULT_FIXTURE.read_text())
        row = next(item for item in workload["requests"] if item["split"] == "final_evaluation")
        options = [item["optionId"] for item in json.loads(DEFAULT_OPTIONS.read_text())["options"]]
        before = {name: _choice(name, row, options) for name in STRATEGIES}
        changed = deepcopy(row)
        for outcome in changed["outcomes"].values():
            outcome["utility"] = 1 - outcome["utility"]
            outcome["status"] = "served" if outcome["status"] == "failed" else outcome["status"]
        after = {name: _choice(name, changed, options) for name in STRATEGIES}
        self.assertEqual(before, after)

    def test_fixture_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            altered = json.loads(DEFAULT_FIXTURE.read_text())
            altered["requests"][0]["taskFamily"] = "tampered"
            path = Path(directory) / "workload.json"
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ExperimentConfigurationError, "hash"):
                run_baselines(fixture_path=path)

    def test_documented_offline_command_emits_stable_tables(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            command = [sys.executable, "-m", "iceberg_router.experiments.baseline"]
            environment = {"PYTHONPATH": str(BASE / "src")}
            for output in (first, second):
                subprocess.run(command + ["--output", output], cwd=BASE,
                               env=environment, check=True, capture_output=True, text=True)
            self.assertEqual((Path(first) / "report.json").read_bytes(),
                             (Path(second) / "report.json").read_bytes())
            self.assertEqual((Path(first) / "table.md").read_bytes(),
                             (Path(second) / "table.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
