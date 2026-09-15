# Baseline comparison matrix

Every upstream column below is a study target, not a verified result. `Unknown`
must remain unknown until pinned source and, where applicable, an executed offline
test provide evidence.

| Baseline | Decision unit | Expected-cost role | Liability bound | Feedback / outcome assumption | Conditional trace | Intended boundary |
|---|---|---|---|---|---|---|
| Fixed model | One configured option | Direct estimate | Common guard required | Observe only executed option | Single attempt | Iceberg-owned reference baseline |
| Task rule | Deterministic eligible option | Per-option estimate | Common guard required | Observe only executed option | Single attempt | Iceberg-owned reference baseline |
| RouteLLM | Weak/strong model threshold (workspace description) | Unknown | Unsupported/unverified | Preference-vs-correctness semantics unknown | Likely one model call; verify | Isolated policy adapter |
| Cascade Routing | Stop/continue and answer choice (workspace description) | Predicted cost role unknown | Unsupported/unverified | Response-table/training visibility unknown | Intended sequential path; verify | Isolated policy adapter |
| R2-Router | `(model, output budget)` (workspace description) | Predicted cost role unknown | Token limit is not yet a money bound | Quality labels/artifacts unknown | Likely one selected pair; verify | Isolated policy adapter |
| LLMRouter | Configurable router (workspace description) | Unknown | Unsupported/unverified | Varies by algorithm; inspect one | Unknown | Minimal interface adapter |
| WISERouter paper reproduction | Workload allocation (workspace description) | Expected cost reported by workspace | No bound established | Offline estimates/exploration reported; verify | Unknown | Paper-faithful isolated baseline |
| Iceberg common-guard variant | Same native choice if admitted | Selection estimate | Required checked upper liability | Executed outcomes only; missing explicit | Full authorized trace | Iceberg-owned wrapper, separately named |

## Fair-comparison invariants

- Freeze the same original workload and option definitions for every mechanism.
- Give comparators the same eligibility information and no future-query visibility.
- Apply one authoritative admission governor, while logging native selections that
  it blocks rather than rewriting them as upstream decisions.
- Charge routing, probe, embedding, retrieval, verification, retries, sentinels,
  and execution to explicit accounts.
- Report utility, actual cost, pending liability, served coverage, deferrals, and
  uncertainty over the original-workload denominator.
- Never splice independent stored model outputs into a claimed executed cascade.
