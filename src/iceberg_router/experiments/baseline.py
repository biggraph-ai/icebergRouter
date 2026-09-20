"""Frozen synthetic baseline experiment used to validate comparison mechanics."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import platform
import random
from statistics import mean
from typing import Mapping


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = ROOT / "fixtures" / "workloads" / "synthetic-baseline-v1.json"
DEFAULT_OPTIONS = ROOT / "fixtures" / "options" / "portfolio-v1.json"
DEFAULT_PROVENANCE = ROOT / "provenance" / "baseline-v1.json"
STRATEGIES = (
    "fixed-cheap",
    "feasible-mixture",
    "task-feature-control",
    "wr-paper-reproduction",
    "wr-plus-common-guard",
    "wr-path-plus-common-guard",
)


class ExperimentConfigurationError(ValueError):
    """A frozen experiment artifact is inconsistent or incomplete."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _hash(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _load(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _choice(strategy: str, row: Mapping[str, object], options: list[str]) -> str:
    family = str(row["taskFamily"])
    if strategy == "fixed-cheap":
        return "cheap-short-v1"
    if strategy == "feasible-mixture":
        eligible = [item for item in options if row["outcomes"][item]["eligible"]]
        digest = sha256(f"baseline-seed-v1:{row['requestId']}".encode()).digest()
        return eligible[int.from_bytes(digest, "big") % len(eligible)]
    if strategy == "task-feature-control":
        return {
            "arithmetic": "checked-repair-v1",
            "document": "retrieval-check-v1",
            "classification": "strong-short-v1",
        }[family]
    # These are explicitly named local adaptations, not author code.  Choices use
    # frozen calibration scores, never final labels or counterfactual utilities.
    scores = row["policyVisibleScores"]
    expected_costs = row["policyVisibleExpectedCostNanos"]
    within_round_budget = [item for item in options if expected_costs[item] <= 40]
    if strategy == "wr-paper-reproduction":
        return max(within_round_budget, key=lambda item: (scores[item], -options.index(item)))
    if strategy == "wr-plus-common-guard":
        feasible = [item for item in within_round_budget if row["outcomes"][item]["eligible"]]
        return max(feasible, key=lambda item: (scores[item], -options.index(item)))
    if strategy == "wr-path-plus-common-guard":
        path_options = {
            "arithmetic": ("checked-repair-v1", "strong-short-v1"),
            "document": ("retrieval-check-v1", "checked-repair-v1"),
            "classification": ("strong-short-v1", "deterministic-short-v1"),
        }[family]
        feasible = [item for item in path_options if row["outcomes"][item]["eligible"]]
        return max(feasible, key=lambda item: scores[item])
    raise ExperimentConfigurationError(f"unknown strategy: {strategy}")


def _interval(values: list[float], *, seed: str) -> list[float]:
    """Deterministic paired bootstrap percentile interval for a mean."""
    if not values:
        return [0.0, 0.0]
    generator = random.Random(seed)
    draws = sorted(
        mean(generator.choice(values) for _ in values) for _ in range(2000)
    )
    return [round(draws[49], 6), round(draws[1949], 6)]


@dataclass(frozen=True)
class _Run:
    rows: tuple[dict[str, object], ...]

    def summary(self) -> dict[str, object]:
        served = [row for row in self.rows if row["status"] == "served"]
        return {
            "requests": len(self.rows),
            "served": len(served),
            "coverage": {"numerator": len(served), "denominator": len(self.rows)},
            "servedTaskQuality": round(mean(row["utility"] for row in served), 6)
            if served else None,
            "utility": sum(row["utility"] for row in self.rows),
            "actualKnownCostNanos": str(sum(row["costNanos"] for row in self.rows)),
            "unresolvedHoldsNanos": str(sum(row["holdNanos"] for row in self.rows)),
            "latencyMillis": sum(row["latencyMillis"] for row in self.rows),
            "failures": sum(row["status"] == "failed" for row in self.rows),
        }


def run_baselines(
    fixture_path: Path = DEFAULT_FIXTURE,
    options_path: Path = DEFAULT_OPTIONS,
    provenance_path: Path = DEFAULT_PROVENANCE,
) -> dict[str, object]:
    workload = _load(fixture_path)
    portfolio = _load(options_path)
    provenance = _load(provenance_path)
    if _hash(workload) != provenance["workloadSha256"]:
        raise ExperimentConfigurationError("workload hash does not match provenance")
    if _hash(portfolio) != provenance["portfolioSha256"]:
        raise ExperimentConfigurationError("portfolio hash does not match provenance")
    options = [item["optionId"] for item in portfolio["options"]]
    if not 5 <= len(options) <= 8 or len(options) != len(set(options)):
        raise ExperimentConfigurationError("portfolio must contain 5-8 unique options")
    families = {row["taskFamily"] for row in workload["requests"]}
    if not 2 <= len(families) <= 3:
        raise ExperimentConfigurationError("workload must contain 2-3 task families")
    if {row["split"] for row in workload["requests"]} != {
        "train", "calibration", "probe", "final_evaluation"
    }:
        raise ExperimentConfigurationError("all frozen experiment splits are required")
    final = [row for row in workload["requests"] if row["split"] == "final_evaluation"]
    runs: dict[str, _Run] = {}
    for strategy in STRATEGIES:
        rows = []
        for item in final:
            option = _choice(strategy, item, options)
            outcome = item["outcomes"][option]
            status = outcome["status"] if outcome["eligible"] else "deferred"
            rows.append({
                "requestId": item["requestId"], "optionId": option, "status": status,
                "utility": outcome["utility"] if status == "served" else 0,
                "costNanos": outcome["costNanos"] if status != "deferred" else 0,
                "holdNanos": outcome["holdNanos"] if status == "pending" else 0,
                "latencyMillis": outcome["latencyMillis"] if status != "deferred" else 0,
            })
        runs[strategy] = _Run(tuple(rows))
    fixed = runs["fixed-cheap"].rows
    summaries = {}
    for strategy, run in runs.items():
        summary = run.summary()
        differences = [
            float(candidate["utility"] - control["utility"])
            for candidate, control in zip(run.rows, fixed)
        ]
        summary["pairedUtilityDifferenceVsFixed95PercentInterval"] = _interval(
            differences, seed=f"baseline-bootstrap-v1:{strategy}"
        )
        summaries[strategy] = summary
    return {
        "schemaVersion": "baseline-results-v1",
        "evidence": "synthetic-mechanics-only",
        "claims": {"modelSuperiority": False, "icebergAdvantage": False,
                   "inheritedWiserouterTheorem": False},
        "seed": provenance["seed"],
        "fixtureHashes": {"workload": _hash(workload), "portfolio": _hash(portfolio)},
        "splitHash": _hash([(row["requestId"], row["split"]) for row in workload["requests"]]),
        "environment": {"python": platform.python_version(), "implementation": platform.python_implementation()},
        "costPermissions": provenance["costPermissions"],
        "sharedComparisonContract": provenance["sharedComparisonContract"],
        "experimentAccountCostsNanos": {
            "training": "0", "calibration": "0", "probe": "0",
            "feature": "0", "operationalChecker": "0", "serving": "0",
            "audit": "0", "blindEvaluation": "0"
        },
        "strategies": summaries,
    }


def _markdown(report: Mapping[str, object]) -> str:
    lines = ["# Synthetic baseline mechanics", "", "No model-superiority or Iceberg-advantage claim is made.", "",
             "| strategy | utility | coverage | cost nanos | unresolved holds | latency ms | failures | paired utility CI vs fixed |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in STRATEGIES:
        item = report["strategies"][name]
        coverage = item["coverage"]
        lines.append(f"| {name} | {item['utility']} | {coverage['numerator']}/{coverage['denominator']} | {item['actualKnownCostNanos']} | {item['unresolvedHoldsNanos']} | {item['latencyMillis']} | {item['failures']} | {item['pairedUtilityDifferenceVsFixed95PercentInterval']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "baseline-v1")
    arguments = parser.parse_args(argv)
    report = run_baselines()
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (arguments.output / "table.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
