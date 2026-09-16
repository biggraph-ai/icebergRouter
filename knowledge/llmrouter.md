# Repository study note: llmrouter

Repository URL: https://github.com/ulab-uiuc/LLMRouter.git
Pinned SHA: 02d02f10ab10c930604b82a506b76af337b2982c (enclosing snapshot; upstream SHA unknown)
Reviewed files/symbols/line ranges: `llmrouter/models/meta_router.py:MetaRouter` (11–109); `custom_routers/randomrouter/router.py:RandomRouter` (19–136); `llmrouter/evaluation/batch_evaluator.py:evaluate_batch` (approximately 152–210); configs under `configs/model_config_*`
Paper or upstream documentation: root README inspected; claims below use code unless labeled documented
Code / dataset / checkpoint license status: see reuse/open questions

## Observed responsibility

A broad configurable router toolkit. `MetaRouter` defines routing behavior and the random custom example emits selected model metadata. Evaluation dispatches task metrics.

## Call-chain trace

YAML/model config → router construction → `route_single`/`route_batch` → selected model metadata; separately, evaluation input → named metric → score/error. It does not provide the common strict budget ledger.

## Inputs, outputs and state

See `source-map.md` for the precise schemas and symbol evidence. Mutable model/config/cache state remains upstream-specific; Iceberg adapters must snapshot versions rather than expose live objects.

## Budget and feedback assumptions

Feedback semantics depend on selected router/task. Batch evaluation can map evaluator exceptions to score 0 plus `evaluation_error`, so operational failure and incorrectness otherwise risk conflation. Cost and counterfactual access are algorithm-specific.

## Reuse decision

Reuse a minimal adapter/interface pattern only; do not adopt every algorithm, GNN, personalization, or multi-round controller. Iceberg owns contracts/governor/outcomes. Root MIT observed; bundled data terms need review.

## Minimal test proposal

After minimal isolated dependencies, load only the random-router synthetic config with a fixed NumPy seed and translate its output into a common decision record. No model/data/network/secret; $0.

## Executed evidence

NOT RUN. On 2026-09-15 this pass only read source in the supplied Linux workspace. No dependencies were installed; no upstream script, model, dataset, checkpoint, service, network request, or paid call was executed.

## Open questions

Upstream SHA, bundled dataset terms, exact configuration registry behavior, dependency footprint, and per-router calls/cost/feedback assumptions.
