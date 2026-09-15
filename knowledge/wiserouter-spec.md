# WISERouter paper specification (pre-implementation)

Paper: `2607.23765v1.pdf` (arXiv v1), inspected locally; no author-linked code
verified. Executed evidence: **NOT RUN**.

## Documented mechanism

Sections 3.1–3.2 formulate each query embedding as context, model as action, and
selected model's quality `Y_t` and normalized resource cost `S_t` as bandit
feedback. Only the chosen action is observed. The objective is expected cumulative
quality subject to an expected workload cost budget. ALP converts remaining budget
into a per-remaining-round constraint and includes a null action with zero reward
and cost. Baseline ALP assumes a finite context space with known context
distribution and known context/action expected reward and cost.

Section 4 replaces those assumptions in two steps: embed and cluster historical
queries into finite contexts (assuming queries in a cluster share expected reward
and cost), then either estimate statistics from historical data (`WR-Offline`) or
learn them under one shared budget (`WR-Online`). WR-Online uses epsilon-first
exploration before ALP exploitation. Algorithms 1–2 describe those offline and
online flows. These are paper descriptions, not tested behavior.

## Budget and feedback interpretation

The optimization is explicitly in expectation and its empirical cost is based on
normalized token-price cost. It does **not** establish an invoice liability upper
bound, exact-money arithmetic, atomic reservations, complete interception of
retries/tools, or safe treatment of unknown bills. Its reward examples include
human preference or ground-truth metrics when available; those channels must stay
distinct in Iceberg.

## Reproduction boundaries

1. `wr-paper-reproduction`: transcribe paper equations/algorithms and preserve
   expected-cost behavior, action set, null action, feedback visibility, and stated
   assumptions.
2. `wr-plus-common-guard`: native choice plus Iceberg upper-liability admission;
   do not attribute the guard or its behavior to the authors.
3. `wr-path-adaptation`: frozen bounded compound options replace model actions;
   do not inherit paper regret/empirical claims.

Before coding, independently review exact LP coefficients, budget update order,
cluster assignment, epsilon schedule, estimators, initialization, numerical solver,
ties/infeasibility/zero-mass behavior, and theorem assumptions from the equations
and appendices. The source snapshot contains no verified author implementation.

## Smallest offline reproduction proposal

In a new isolated standard-library test harness after equation transcription, run
`python -m unittest tests.test_wiserouter_tiny -v` over hand-computed one-context,
two-context, null-only, exact-boundary, zero-budget, tie, and seeded exploration
cases. Required artifact: a reviewed local transcription plus fixture checksum.
Network/secrets: none. Maximum expense: $0. Expected result: probabilities, chosen
null actions, observations, and remaining expected budget match hand calculations.
This proposal is not a reproduced paper result.
