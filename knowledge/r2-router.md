# Repository study note: r2-router

Repository URL: https://github.com/UCF-ML-Research/R2-Router.git
Pinned SHA: NOT AVAILABLE (fetch blocked before `FETCH_HEAD`)
Reviewed files/symbols/line ranges: NONE—source was not retrieved
Paper or upstream documentation: workspace manifest/register only; upstream README NOT INSPECTED
Code / dataset / checkpoint license status: NOT REVIEWED

## Observed responsibility

No code behavior was observed. The workspace describes joint model/output-budget
selection and separately reports that an earlier README review found a clone
example naming `jqxue1999/router` and another branch. That discrepancy remains
unresolved and must not be silently normalized.

## Call-chain trace

UNVERIFIED: request/features → candidate `(model, output budget)` scores/costs →
pair selection → bounded generation → result. Inspect `r2_router/router.py`, its
configuration, `route.py`, reproduction files, and `DATA_RELEASE.md`.

## Budget and feedback assumptions

UNKNOWN. Predicted output tokens, requested `max_tokens`, provider-enforced limits,
and invoice liability are distinct until code/provider evidence proves otherwise.

## Reuse decision

Isolated baseline adapter only. Do not load checkpoints until format, provenance,
license, and deserialization risk are reviewed.

## Minimal test proposal

Pass a tiny synthetic quality/cost grid to the smallest inspected selection
function and hand-check the selected model-budget pair, ties, and infeasible pairs.
No checkpoint, model, data download, secret, network, or paid call.

## Executed evidence

Core source-only fetch FAILED with HTTPS CONNECT 403 on 2026-09-15. No upstream
code ran.

## Open questions

Canonical provenance discrepancy, exact SHA/symbols, license and artifact terms,
checkpoint type, token-limit enforcement, retries, cost model, and feedback labels.
