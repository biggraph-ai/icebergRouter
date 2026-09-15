# WISERouter specification status

Paper: https://arxiv.org/html/2607.23765v1
Version requested by the register: arXiv v1 (`2607.23765v1`)
Author-linked implementation: NOT VERIFIED
Executed evidence: NOT RUN

## Evidence classification

The paper could not be retrieved in this environment: both the web retrieval tool
and a direct HTTPS request failed before content was returned. Consequently, no
algorithm, equation, theorem, parameter, or experimental claim is recorded here
as inspected paper evidence. The statements in `STUDY_ORDER.md`—contextual
workload allocation, embedding clusters, offline estimates, exploration before
allocation, and expected-cost optimization—are **workspace descriptions**, not
findings independently verified in this pass.

## Required paper review

At minimum, inspect sections 3–4, Algorithms 1–2, the assumptions, and the
experimental appendices. Record exact section/equation/algorithm references for:

- decision variables, context, action space, null/abstain action, and constraints;
- how offline reward and expected cost estimates are formed;
- exploration and allocation distributions, including ties and zero-mass cases;
- budget update timing and whether feasibility is in expectation or pathwise;
- feedback observability, missing outcomes, and any stationarity assumptions;
- solver, numerical precision, randomness, and convergence assumptions; and
- datasets, baselines, metrics, uncertainty reporting, and excluded costs.

## Reproduction boundaries

Keep three separately named mechanisms:

1. `wr-paper-reproduction`: only behavior supported by inspected paper evidence.
2. `wr-plus-common-guard`: the reproduction subjected to Iceberg's shared
   upper-liability admission guard; do not attribute this guard to the paper.
3. `wr-path-adaptation`: an equal-option bounded-policy adaptation; do not transfer
   paper guarantees to it.

No implementation should begin from this note. Paper retrieval and review are
blocking prerequisites.

## Minimal test proposal

After review, implement tiny deterministic tables only: one option, equal-valued
options, a null action, zero budget, an expected-cost boundary, and a seeded
exploration draw. Compare hand-computed distributions and budget updates with the
paper. This requires no model, dataset, secret, network call, or paid operation.
