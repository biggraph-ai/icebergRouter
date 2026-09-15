# Repository study note: r2-router

Repository URL: https://github.com/UCF-ML-Research/R2-Router.git
Pinned SHA: 02d02f10ab10c930604b82a506b76af337b2982c (enclosing snapshot; upstream SHA unknown)
Reviewed files/symbols/line ranges: `r2_router/router.py:R2Router.from_pretrained` (80–139), `route` (248–325), `generate` (329–402), `route_and_generate` (404–440); `README.md`; `DATA_RELEASE.md`; `artifacts/LICENSE_NOTE.md`
Paper or upstream documentation: root README inspected; claims below use code unless labeled documented
Code / dataset / checkpoint license status: see reuse/open questions

## Observed responsibility

Joint model/output-effort selector using Ridge predictions. It enumerates finite and “unlimited” options and maximizes a quality/cost scalarization.

## Call-chain trace

query → local/remote embedding → approximate input tokens → Ridge quality/token predictions → float predicted cost/risk → best pair → HTTP generation → usage. Finite “budget” is inserted only into a system prompt; no output-token request cap is sent.

## Inputs, outputs and state

See `source-map.md` for the precise schemas and symbol evidence. Mutable model/config/cache state remains upstream-specific; Iceberg adapters must snapshot versions rather than expose live objects.

## Budget and feedback assumptions

Cost is an estimate from configured token prices; it is not liability admission. Missing usage keys become zero. Joblib loading can execute unsafe serialized content and optional paths download from Hugging Face.

## Reuse decision

Reference selector only pending license/provenance. A safe adapter must use supplied arrays/stubs and a separately bounded executor. No root code license found; artifact note does not resolve upstream rights.

## Minimal test proposal

Without loading checkpoints, construct stub predictors/config in an isolated test and call `route` on one fixed embedding; cover ties, finite/unlimited, and infeasible-under-common-guard cases. No network/secret; $0.

## Executed evidence

NOT RUN. On 2026-09-15 this pass only read source in the supplied Linux workspace. No dependencies were installed; no upstream script, model, dataset, checkpoint, service, network request, or paid call was executed.

## Open questions

README canonical-repository discrepancy; upstream SHA; code/checkpoint licenses/hashes; joblib provenance; prompt-only cap; float rounding and missing usage semantics.
