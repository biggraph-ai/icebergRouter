# Repository study note: cascade-routing

Repository URL: https://github.com/eth-sri/cascade-routing.git
Pinned SHA: NOT AVAILABLE (fetch blocked before `FETCH_HEAD`)
Reviewed files/symbols/line ranges: NONE—source was not retrieved
Paper or upstream documentation: workspace manifest/register only; upstream README NOT INSPECTED
Code / dataset / checkpoint license status: Apache-2.0 is reported by the workspace; NOT VERIFIED at a pinned commit

## Observed responsibility

No implementation behavior was observed. The workspace describes a sequential
baseline that can stop, call another model, and select a final answer.

## Call-chain trace

UNVERIFIED. Inspect `cascade_router.py`, `baseline_cascader.py`, quality/cost
computers, and lambda strategy to identify response availability, predicted
quality/cost, stop/continue choice, answer selection, and exhausted-option behavior.

## Budget and feedback assumptions

UNKNOWN. Determine whether cost is observed or predicted, whether optimization is
expected-cost only, which counterfactual responses training requires, and how a
missing response or failed call is represented. No strict budget guarantee is
currently supported by evidence.

## Reuse decision

Isolated sequential baseline behind Iceberg contracts. Preserve native decisions
in traces and separately label common-guard blocks.

## Minimal test proposal

Use a hand-written response table covering immediate stop, one continuation,
missing response, and exhausted liability. Exercise only inspected pure selection
methods in an isolated environment. No provider, dataset, secret, or paid call.

## Executed evidence

Core source-only fetch FAILED with HTTPS CONNECT 403 on 2026-09-15. No upstream
code ran.

## Open questions

Exact SHA/symbols, notices, training information, stopping equality, answer chooser,
retry paths, missing responses, accounting units, and enforceability of costs.
