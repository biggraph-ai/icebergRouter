# Baseline experiment v1

This is a **synthetic mechanics experiment**, not a benchmark or evidence that one
model/router is better. It uses three declared task families, six frozen option
specifications, and frozen train/calibration/probe/final-evaluation splits.

Run from a clean product checkout without installation, credentials, network, model
artifacts, or paid calls:

```sh
PYTHONPATH=src python -m iceberg_router.experiments.baseline --output results/baseline-v1
```

The command verifies canonical SHA-256 hashes from `provenance/baseline-v1.json`,
then emits `report.json` and `table.md`. All controls receive the same portfolio,
resource limits, checker access, workload visibility, and declared common guard.
Every final request remains in the denominator. Costs, unresolved holds, latency,
failures, served-task quality, coverage, utility, and deterministic paired bootstrap
intervals are reported.

## Strategy interpretations

* `fixed-cheap`, `feasible-mixture`, and `task-feature-control` exercise the simple
  controls first.
* `wr-paper-reproduction` is a local transcription of the reviewed score/rank
  interpretation recorded in the WISERouter study note. It is not official author
  code and does not inherit a theorem.
* `wr-plus-common-guard` applies the identical eligibility guard to that local
  interpretation.
* `wr-path-plus-common-guard` additionally restricts candidates to a declared
  task-family path, then applies the same guard.

The policy-visible fixture contains frozen calibration scores only. Final utilities
and counterfactual outcomes are consumed by the evaluator after selection, never by
the strategy. The synthetic matrix is not described as an executed workflow trace.

## Deliberately blocked acceptance item

A real conditional-workflow run is **not** part of this offline PR. It requires a
separately reviewed provider/fixture authorization, tariff, artifact provenance,
secret/network permission, expected maximum expense, and isolated command. Until
that approval exists, no real trace-plumbing or routing-quality claim is made.
