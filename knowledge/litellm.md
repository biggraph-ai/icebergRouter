# Repository study note: litellm

Repository URL: https://github.com/BerriAI/litellm.git
Pinned SHA: 02d02f10ab10c930604b82a506b76af337b2982c (enclosing snapshot; upstream SHA unknown)
Reviewed files/symbols/line ranges: `litellm/router.py:Router.__init__` (704–1028); `router_utils/get_retry_from_policy.py` (1–63); `proxy/spend_tracking/budget_reservation.py:reserve_budget_for_request` (201–300), reconciliation/release (327–370), `estimate_request_max_cost` (1080+); `proxy/hooks/max_budget_limiter.py` (15–84)
Paper or upstream documentation: root README inspected; claims below use code unless labeled documented
Code / dataset / checkpoint license status: see reuse/open questions

## Observed responsibility

Provider/gateway normalization plus routing, retry/fallback, cost estimation, and proxy budget counters. It is a transport candidate, not proof of strict invoice-bounded execution.

## Call-chain trace

normalized request → optional estimate/counter reservation → provider/router attempt → retry/fallback/stream handling → usage/cost callbacks → reservation reconciliation/release. Multiple fallback classes and inherited retry defaults exist.

## Inputs, outputs and state

See `source-map.md` for the precise schemas and symbol evidence. Mutable model/config/cache state remains upstream-specific; Iceberg adapters must snapshot versions rather than expose live objects.

## Budget and feedback assumptions

Reservation uses float estimates. Unknown/nonpositive estimates skip reservation; write failure may continue unless fail-closed; non-strict overage can resize. This is not Iceberg exact-money upper-liability accounting. Cancellation/reconciliation behavior needs mock characterization.

## Reuse decision

Replaceable adapter only, restricted to non-enterprise surfaces. Iceberg owns authorization and attempt IDs, fixed-unit ledger, pending unknown usage, and policy trace. Root says non-enterprise MIT; enterprise has separate restrictive terms.

## Minimal test proposal

In a separately pinned environment, local fake provider only: success, timeout with absent usage, stream cancellation, one retry, fallback, duplicate reconciliation, unavailable counter. Explicitly disable outbound network; no secrets; $0. Assert every physical attempt and unresolved hold is visible.

## Executed evidence

NOT RUN. On 2026-09-15 this pass only read source in the supplied Linux workspace. No dependencies were installed; no upstream script, model, dataset, checkpoint, service, network request, or paid call was executed.

## Open questions

Upstream SHA, rapidly changing semantics, default retry sources, streaming settlement, provider-specific non-token charges, atomicity/durability backend, enterprise boundary.
