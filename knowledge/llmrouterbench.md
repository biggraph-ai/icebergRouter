# Repository study note: llmrouterbench

Repository URL: https://github.com/ynulihao/LLMRouterBench.git
Pinned SHA: NOT AVAILABLE (fetch blocked before `FETCH_HEAD`)
Reviewed files/symbols/line ranges: NONE—source was not retrieved
Paper or upstream documentation: workspace manifest/register only; upstream README NOT INSPECTED
Code / dataset / checkpoint license status: NOT REVIEWED

## Observed responsibility

No implementation responsibility was observed. The workspace describes this as an
offline dataset/evaluation reference. That description is not a code finding.

## Call-chain trace

UNVERIFIED. In particular, no evidence yet establishes whether a row is an
independent model outcome, what creates cost/score fields, or whether any stored
answers can represent conditional execution.

## Budget and feedback assumptions

UNKNOWN. Do not treat table cost as an enforceable liability bound, missing cells
as zero cost or acceptance, or independent rows as executed workflow branches.

## Reuse decision

Reference only until source, data terms, schemas, and splits are reviewed at a
pinned commit. Dataset files must not be copied merely because code is public.

## Minimal test proposal

After retrieval, parse a tiny synthetic row fixture through the smallest inspected
evaluation entry point and hand-check fixed-model and task-rule summaries. Python
environment isolated per upstream requirements; no network, secrets, models, or
paid calls. This is a schema/evaluator test, not a benchmark reproduction.

## Executed evidence

`python fetch_references.py --groups core --clone`, 2026-09-15, provided Linux
container: FAILED at HTTPS CONNECT with status 403. No upstream command ran.

## Open questions

Exact SHA, file/symbol map, repository license, dataset terms and availability,
split leakage, cost provenance, missing-output handling, and evaluator coverage.
