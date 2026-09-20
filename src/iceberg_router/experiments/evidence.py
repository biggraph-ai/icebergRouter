"""Controlled synthetic PR 8 evidence-acquisition study."""

from __future__ import annotations

import argparse
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from iceberg_router.contracts.identifiers import OptionId, RequestId
from iceberg_router.contracts.money import Nanodollars
from iceberg_router.core.probes import ProbeCandidate, ProbeVariant, plan_probes
from iceberg_router.core.statistics import FrozenStrataEstimator, OutcomeCostObservation
from .baseline import DEFAULT_FIXTURE, DEFAULT_OPTIONS, ROOT, _load


VARIANTS = tuple(ProbeVariant)
UTILITY_VALUE_NANOS = 100
PROBE_CAP_NANOS = 200
DEFAULT_PROVENANCE = ROOT / "provenance" / "evidence-v1.json"


def _observation(row, option: str) -> OutcomeCostObservation:
    outcome = row["outcomes"][option]
    return OutcomeCostObservation(
        str(row["taskFamily"]), OptionId(option), bool(outcome["utility"]),
        Nanodollars(int(outcome["costNanos"])),
    )


def _allocator(estimator: FrozenStrataEstimator, context: str, options: list[str]) -> str:
    """The one downstream allocator shared unchanged by every probe variant."""
    return max(options, key=lambda option: (
        estimator.estimate(context, OptionId(option)).success_probability,
        -estimator.estimate(context, OptionId(option)).mean_cost.value,
        option,
    ))


def run_evidence_study(
    fixture_path: Path = DEFAULT_FIXTURE,
    options_path: Path = DEFAULT_OPTIONS,
    provenance_path: Path = DEFAULT_PROVENANCE,
) -> dict[str, object]:
    provenance = _load(provenance_path)
    fixture_hash = sha256(fixture_path.read_bytes()).hexdigest()
    options_hash = sha256(options_path.read_bytes()).hexdigest()
    if fixture_hash != provenance["inputs"]["workloadFileSha256"]:
        raise ValueError("workload file hash does not match evidence provenance")
    if options_hash != provenance["inputs"]["portfolioFileSha256"]:
        raise ValueError("portfolio file hash does not match evidence provenance")
    workload = _load(fixture_path)
    portfolio = _load(options_path)
    options = [item["optionId"] for item in portfolio["options"] if item["maxAttempts"] > 0]
    calibration = [row for row in workload["requests"] if row["split"] == "calibration"]
    probes = [row for row in workload["requests"] if row["split"] == "probe"]
    final = [row for row in workload["requests"] if row["split"] == "final_evaluation"]
    calibration_rows = tuple(_observation(row, option) for row in calibration for option in options)
    base = FrozenStrataEstimator(calibration_rows, version="calibration-v1")
    candidates = tuple(
        ProbeCandidate(
            RequestId(row["requestId"]), str(row["taskFamily"]), OptionId(option),
            Nanodollars(int(row["policyVisibleExpectedCostNanos"][option])),
            int(base.estimate(str(row["taskFamily"]), OptionId(option)).probability_standard_error * Decimal(1_000_000)),
        )
        for row in probes for option in options
    )
    by_request = {row["requestId"]: row for row in probes}
    results = {}
    selections = {}
    calibration_cost = sum(row.actual_cost.value for row in calibration_rows)
    for variant in VARIANTS:
        plan = plan_probes(variant, candidates, cap=Nanodollars(PROBE_CAP_NANOS), seed="probe-study-v1")
        additions = tuple(_observation(by_request[item.request_id.value], item.option_id.value) for item in plan.selected)
        estimator = base if not additions else base.updated(additions, version=f"{variant.value}-v1")
        chosen = tuple(_allocator(estimator, str(row["taskFamily"]), options) for row in final)
        selections[variant.value] = chosen
        evaluated = [row["outcomes"][option] for row, option in zip(final, chosen)]
        utility = sum(int(item["utility"]) for item in evaluated)
        serving_cost = sum(int(item["costNanos"]) for item in evaluated)
        probe_cost = sum(row.actual_cost.value for row in additions)
        served = sum(item["status"] == "served" for item in evaluated)
        results[variant.value] = {
            "probes": len(additions),
            "predeclaredProbeCapNanos": str(PROBE_CAP_NANOS),
            "probeReservedNanos": plan.reserved.to_json(),
            "probeActualCostNanos": str(probe_cost),
            "calibrationCostNanos": str(calibration_cost),
            "servingCostNanos": str(serving_cost),
            "totalDecisionAndServingCostNanos": str(calibration_cost + probe_cost + serving_cost),
            "utility": utility,
            "netUtilityNanos": str(utility * UTILITY_VALUE_NANOS - calibration_cost - probe_cost - serving_cost),
            "coverage": {"numerator": served, "denominator": len(final)},
            "stoppingRule": plan.stopping_rule,
            "intrinsicOutcomeVariance": {
                f"{context}/{option.value}": format(estimate.intrinsic_variance, "f")
                for (context, option), estimate in estimator.estimates.items()
            },
            "estimatedProbabilityStandardError": {
                f"{context}/{option.value}": format(estimate.probability_standard_error, "f")
                for (context, option), estimate in estimator.estimates.items()
            },
        }
    zero = results[ProbeVariant.ZERO.value]
    for name, item in results.items():
        item["netUtilityDifferenceVsZeroNanos"] = str(
            int(item["netUtilityNanos"]) - int(zero["netUtilityNanos"])
        )
    coverage_values = {tuple(item["coverage"].values()) for item in results.values()}
    repaid = any(int(item["netUtilityDifferenceVsZeroNanos"]) > 0 for name, item in results.items() if name != ProbeVariant.ZERO.value)
    return {
        "schemaVersion": "evidence-acquisition-v1",
        "evidence": "synthetic-mechanics-only",
        "downstreamAllocator": "empirical-success-then-cost-v1",
        "downstreamAllocatorHeldConstant": True,
        "matchedCoverage": len(coverage_values) == 1,
        "informationAccess": "calibration plus own selected probes; final labels withheld until evaluation",
        "variants": results,
        "stopRuleConclusion": "retain-simple-probes" if repaid else "null-result-simplify-to-zero-probe",
        "evidenceAcquisitionRepaidCost": repaid,
        "claims": {"realModelEvidence": False, "icebergAdvantage": False},
        "inputFileHashes": {"workload": fixture_hash, "portfolio": options_hash},
        "permissions": provenance["permissions"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "evidence-v1")
    args = parser.parse_args(argv)
    report = run_evidence_study()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
