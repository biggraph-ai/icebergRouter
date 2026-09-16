# Blocked items and discrepancies

None of these blocks reconnaissance; they block faithful reproduction, reuse, or
implementation approval as stated.

1. **Upstream commit provenance:** the six folders have no nested `.git` data and
   no vendor lock. Only enclosing commit
   `02d02f10ab10c930604b82a506b76af337b2982c` is verifiable. Obtain canonical URL,
   original SHA, archive hash, notice hash, and modification record for each.
2. **Missing root licenses:** no root license was found for `LLMRouterBench` or
   `R2-Router`. Embedded baseline licenses do not license the parent repository.
   R2's artifact note explicitly leaves upstream rights to their providers.
3. **Artifact/data terms:** RouteLLM Hugging Face datasets/checkpoints, Cascade
   response data, LLMRouter bundled datasets, LLMRouterBench datasets, and all R2
   joblib checkpoints need independent provenance, checksum, format, and license
   review. Presence in Git is not copying/redistribution permission.
4. **R2 provenance discrepancy:** its README clone command names
   `jqxue1999/router` branch `r2-router`, while the study manifest names
   `UCF-ML-Research/R2-Router`. Resolve authorship/history; do not substitute one.
5. **R2 unsafe budget semantics:** prompt-only length instruction does not enforce
   an output cap; missing provider usage is coerced to zero. A faithful baseline
   and a safe adapted executor must be separately named.
6. **Cascade ambiguity/possible defect:** characterize empty-answer behavior in
   `select_answer`, tie randomization, `gamma`, response-table visibility, and cost
   units before claiming parity.
7. **LLMRouterBench discrepancy:** the baseline schema documents a float USD cost,
   but no provenance/version for that tariff is carried by `BaselineRecord`; some
   evaluators can call graders or execute generated code. Select a safe, offline
   subset rather than treating all evaluation modules as pure.
8. **Hidden attempts:** LiteLLM defaults can inherit retries and expose several
   fallback classes; RouteLLM delegates execution to LiteLLM. Exact sync/async,
   streaming, cancellation, and fallback attempt identities require characterization.
9. **Unsupported strict budget guarantee:** LiteLLM reservation can skip unknown
   estimates, use float money, continue when a write is unavailable unless
   fail-closed, or resize in non-strict mode. No reviewed upstream baseline proves
   `confirmed + outstanding <= budget` under Iceberg assumptions.
10. **WISERouter reproduction details:** paper v1 is present and §§3–4 were read,
    but exact equation transcription, solver/tie/zero-mass numerical behavior,
    hyperparameters, and author-linked code remain unresolved. Do not claim an
    author-code reproduction.
11. **Policy-development gate not met:** no upstream source has been installed or
    run, and no dataset split/artifact lock or baseline parity result exists. Local
    contract, budget-governor, bounded-graph, scripted-executor, audit, control,
    adapter-boundary, orchestration, evaluation, and feedback-snapshot fixtures now
    exist through Increment 10, but
    upstream reproduction and Iceberg-specific acquisition policy implementation
    remain prohibited until their applicable gates pass.

## Explicitly not blocked / corrected stale status

The audited DOCX, all six source snapshots, and WISERouter PDF are present. Earlier
notes claiming they were absent or network-blocked described a prior workspace
state and are superseded by this pass. No download is needed or authorized.
