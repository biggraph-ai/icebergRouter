# Repository study note: llmrouterbench

Repository URL: https://github.com/ynulihao/LLMRouterBench.git
Pinned SHA: 02d02f10ab10c930604b82a506b76af337b2982c (enclosing snapshot; upstream SHA unknown)
Reviewed files/symbols/line ranges: `baselines/schema.py:BaselineRecord` (13–98); `baselines/data_loader.py:BaselineDataLoader` (18–260+); `baselines/aggregators.py:BaselineAggregator` (16–180+)
Paper or upstream documentation: root README inspected; claims below use code unless labeled documented
Code / dataset / checkpoint license status: see reuse/open questions

## Observed responsibility

Offline single-generation outcome schema, filtering/loading, and aggregation. A row represents one model result and float USD cost; hindsight oracle groups independent rows. It does not encode a conditional workflow.

## Call-chain trace

result JSON → filtered `BaselineRecord` → grouped score/token/cost statistics or hindsight oracle. Dataset evaluator/generator paths are outside this pure aggregation chain.

## Inputs, outputs and state

See `source-map.md` for the precise schemas and symbol evidence. Mutable model/config/cache state remains upstream-specific; Iceberg adapters must snapshot versions rather than expose live objects.

## Budget and feedback assumptions

Stored ground truth/score is offline feedback. Cost is a float observation without an enforceable bound or tariff version in the row. Missing/corrupt files may be skipped; evaluator-specific failures vary.

## Reuse decision

Reference/evaluator adapter only. Keep exact accounting, split registry, option traces, and coverage in Iceberg. No root license was found; embedded baseline notices and dataset terms do not license the whole tree.

## Minimal test proposal

In a fresh isolated environment, after dependency review: `python -m unittest <new characterization module>` against three hand-written JSON records for two models and one missing record. Source plus fixture only; no network/secrets; $0. Expect fixed-model aggregates and explicitly hindsight-only oracle.

## Executed evidence

NOT RUN. On 2026-09-15 this pass only read source in the supplied Linux workspace. No dependencies were installed; no upstream script, model, dataset, checkpoint, service, network request, or paid call was executed.

## Open questions

Root license absent; dataset provenance/splits and tariff source unknown; evaluator modules include generated-code and model-judge paths and are not all safe offline.
