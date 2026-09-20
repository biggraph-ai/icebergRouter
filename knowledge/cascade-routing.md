# Repository study note: cascade-routing

Repository URL: https://github.com/eth-sri/cascade-routing.git
Pinned SHA: 02d02f10ab10c930604b82a506b76af337b2982c (enclosing snapshot; upstream SHA unknown)
Reviewed files/symbols/line ranges: `src/selection/cascade_router.py:CascadeRouter` (6–290+); `baseline_cascader.py:BaselineCascader` (6–170+); `quality_computer.py` (9–175+); `cost_computer.py` (6–82); `lambda_strategy.py` (6–220+)
Paper or upstream documentation: root README inspected; claims below use code unless labeled documented
Code / dataset / checkpoint license status: see reuse/open questions

## Observed responsibility

Sequentially chooses another model or stops, then selects an answer among models already represented in the response table. It compares predicted supermodel quality against lambda-weighted summed predicted cost.

## Call-chain trace

question + partial `model_answers` (`None`=unrun) → quality/cost prediction → supermodel search → next model or stop → repeat → predicted-quality answer selection. `fit` tunes lambdas against `max_expected_cost` and mixes cheap/expensive tie solutions.

## Inputs, outputs and state

See `source-map.md` for the precise schemas and symbol evidence. Mutable model/config/cache state remains upstream-specific; Iceberg adapters must snapshot versions rather than expose live objects.

## Budget and feedback assumptions

Training/evaluation can accept full response tables plus quality/cost measures. That counterfactual visibility is not a live trace. Budget is expected average cost; random `gamma` mixing and float arithmetic do not establish a pathwise cap.

## Reuse decision

Isolated table-driven reproduction. Preserve native policy and separately apply common guard. Apache-2.0 root text observed. Do not silently fix the apparent empty-answer double append at lines 242–243.

## Minimal test proposal

In its own reviewed environment: pure selector characterization on a 2-query × 2-model synthetic response table for stop, continue, no-answer, and max-depth. Seed NumPy; no network/secrets; $0. Hand-check calls and table cost. This is simulation, not live cascade quality.

## Executed evidence

NOT RUN. On 2026-09-15 this pass only read source in the supplied Linux workspace. No dependencies were installed; no upstream script, model, dataset, checkpoint, service, network request, or paid call was executed.

## Open questions

Upstream SHA, dataset/model terms, units, exact tie behavior, possible `select_answer` defect, and training split visibility.
