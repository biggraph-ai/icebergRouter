# Repository study note: llmrouter

Repository URL: https://github.com/ulab-uiuc/LLMRouter.git
Pinned SHA: NOT AVAILABLE (fetch blocked before `FETCH_HEAD`)
Reviewed files/symbols/line ranges: NONE—source was not retrieved
Paper or upstream documentation: workspace manifest/register only; upstream README NOT INSPECTED
Code / dataset / checkpoint license status: MIT is reported by the workspace; NOT VERIFIED at a pinned commit

## Observed responsibility

No code behavior was observed. The workspace describes common router interfaces,
configurable baselines, and experiment adapters.

## Call-chain trace

UNVERIFIED. Locate the router interface, one simple classifier, configuration
loading, and one evaluation entry point; then map request → features → policy
decision → externally executed option → common outcome without adopting the full
algorithm collection.

## Budget and feedback assumptions

UNKNOWN. Inspect interfaces for implicit API execution, retries, cached outcomes,
cost units, preference labels, missing feedback, and counterfactual visibility.

## Reuse decision

Adapter/reference candidate, not the authoritative Iceberg engine. Reuse only the
minimal interface behavior permitted by verified license and provenance.

## Minimal test proposal

Instantiate one inspected simple router against a tiny synthetic fixture and map
its selection into the proposed common decision record. Isolated dependencies;
no provider/model, dataset, secret, network, or paid call.

## Executed evidence

Core source-only fetch FAILED with HTTPS CONNECT 403 on 2026-09-15. No upstream
code ran.

## Open questions

Exact SHA/symbols, license/notices and bundled terms, interface contract,
configuration defaults, hidden calls/retries, cost support, and outcome semantics.
