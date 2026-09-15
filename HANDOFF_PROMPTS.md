# Prompts to give the coding agent

## Prompt 1 — repository reconnaissance only
You are preparing to implement IcebergRouter. Read AGENTS.md, requirements/PLAN_CONSTRAINTS.md and STUDY_ORDER.md first. The authoritative user document is IcebergRouter_Implementation_Blueprint_v2_Audited.docx; use it when available and identify any conflicts.

Do not implement Iceberg yet. Do not execute external repo scripts, install dependencies, fetch weights/data, start services, load checkpoints or make paid calls. Inspect the six core reference checkouts and the WISERouter paper in the stated order. Keep references unchanged.

For each repository, write knowledge/<repo>.md using templates/repo_note.md. Ground technical findings in exact commit, file and symbol/line references. Produce knowledge/source-map.md, knowledge/baseline-matrix.md, knowledge/assumption-register.md and knowledge/blocked-items.md. Flag mismatched repo URLs, unknown licenses, omitted datasets, hidden retries and unsupported budget guarantees. Distinguish documented behavior from inspected code and from behavior actually executed. Stop after the report; do not fill gaps by inventing an upstream API or result.

## Prompt 2 — plan minimal reproductions
Use the reconnaissance outputs. Propose the smallest offline tests that exercise a simple threshold router, a cascade's stop/continue behavior, model-plus-token-budget selection and a paper-based WISERouter allocator. Give exact reviewed entry points, separate environment requirements, dependencies, artifacts, potential costs and expected outputs. Mock tests must be labeled as mock tests. Keep original method behavior, our common-guard additions and WR-Path adaptations separately named. Do not launch full benchmark sweeps.

## Prompt 3 — build the governed baseline harness
After approval of the reproduction plan, implement the common Python option/execution/ledger contracts and the ACCEPTANCE_GATES fixtures with mock providers first. Use exact money, explicit conditional branches, bounded attempts, immutable identities and pending reconciliation. Write one common outcome format and compute utility/cost/coverage for every baseline on identical options. Do not add the Iceberg acquisition mechanism until the baseline and budget tests pass. Java and TypeScript are thin clients at this stage.

## Prompt 4 — implement the smallest falsifiable Iceberg variant
Implement uniform/stratified probes over the approved finite option pool and compare against the same-option workload allocator. Charge all adaptation costs, freeze splits, and report coverage and uncertainty. Change only the acquisition strategy when adding an active variant. If the method does not improve net utility/cost, report that result and recommend simplification. Do not generate a positive paper narrative in advance of results.
