# Repository study note: routellm

Repository URL: https://github.com/lm-sys/RouteLLM.git
Pinned SHA: NOT AVAILABLE (fetch blocked before `FETCH_HEAD`)
Reviewed files/symbols/line ranges: NONE—source was not retrieved
Paper or upstream documentation: workspace manifest/register only; upstream README NOT INSPECTED
Code / dataset / checkpoint license status: Apache-2.0 is reported by the workspace; NOT VERIFIED at a pinned commit

## Observed responsibility

No code behavior was observed. The workspace characterizes RouteLLM as a
model-selection and threshold-calibration baseline.

## Call-chain trace

Target trace, still UNVERIFIED: request → router feature/score → calibrated
threshold → weak/strong model choice → provider execution → output. The controller,
router implementations, calibration code, evaluation code, and tests remain to be
inspected. Preference prediction must not be relabeled objective correctness.

## Budget and feedback assumptions

UNKNOWN. Threshold calibration must be examined for its cost model, target metric,
training feedback, and whether it offers any per-request liability guarantee.

## Reuse decision

Isolated baseline adapter after inspection; do not adopt its controller as the
common budget governor or claim its score is a success probability.

## Minimal test proposal

At the pinned SHA, import only the smallest scoring/selection boundary in an
isolated environment and use mocked inference with scores immediately below, at,
and above a calibrated threshold. No model/API call, dataset, secret, or paid cost.
This validates branching only, not trained-router quality.

## Executed evidence

Core source-only fetch FAILED with HTTPS CONNECT 403 on 2026-09-15. No upstream
tests or scripts ran.

## Open questions

Exact SHA/symbols, license/notices, score orientation, equality behavior,
calibration objective, model-call retries, usage accounting, and failure fallback.
