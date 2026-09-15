# Repository study note: litellm

Repository URL: https://github.com/BerriAI/litellm.git
Pinned SHA: NOT AVAILABLE (fetch blocked before `FETCH_HEAD`)
Reviewed files/symbols/line ranges: NONE—source was not retrieved
Paper or upstream documentation: workspace manifest/register only; upstream README/docs NOT INSPECTED
Code / dataset / checkpoint license status: mixed licensing boundary reported; NOT REVIEWED

## Observed responsibility

No implementation behavior was observed. The workspace treats LiteLLM as a
replaceable provider gateway whose normalization, billing, retry, streaming, and
failure behavior must be audited rather than trusted as a budget guarantee.

## Call-chain trace

UNVERIFIED. Trace request normalization → provider call/attempt identity → retry or
fallback → streaming/cancellation → usage extraction → pricing → response/error.
Search both library and gateway paths plus tests and current budget documentation.

## Budget and feedback assumptions

UNKNOWN. Provider-reported usage may arrive late or never; timeout/cancellation is
not proof of zero charge. Each retry must remain an independently authorized
liability. No common-ledger or strict-ceiling guarantee is established.

## Reuse decision

Replaceable transport adapter only. Iceberg must own authorization, attempt IDs,
pending reconciliation, exact-money settlement, and decision/outcome logs.

## Minimal test proposal

After inspecting test seams, use a local mock provider for success, timeout with
unknown usage, streaming cancellation, retry, duplicate settlement, and stale
budget state. No external provider, model, dataset, secret, network, or paid call.

## Executed evidence

Core source-only fetch FAILED with HTTPS CONNECT 403 on 2026-09-15. No upstream
code or service ran.

## Open questions

Exact SHA/symbols, license boundaries, pricing versioning, retry/fallback defaults,
attempt IDs, streaming usage, cancellation semantics, and gateway budget races.
