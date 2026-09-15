# Evidence required before Iceberg-specific policy development

| Gate | Evidence | Failure condition |
|---|---|---|
| Source identity | Canonical URL, exact SHA, paths and a provenance note | A similarly named repo is treated as a paper implementation without evidence |
| Scope | Six concise repo notes and the WISERouter specification | Generic summaries without actual source locations |
| Licensing | Code/dataset/checkpoint terms and unreviewed items recorded | Public visibility assumed to mean permission to copy |
| Algorithm comprehension | Stop/continue, threshold and model-budget examples | Inference score described as proof of correctness |
| Budget semantics | Expected cost and upper liability bound are distinct fields | A mean or padded estimate advertised as a hard bound |
| Failure semantics | Concurrent reserve, unknown usage, retry and duplicate-settlement fixtures | Cancellation releases unresolved liabilities |
| Evaluation | Frozen splits, all adaptation costs, coverage, uncertainty plan | Stored independent answers presented as executed dependent workflows |
| Fair baseline | Same options and common admission guard for mechanism comparisons | Iceberg gets tools or future queries that comparators cannot use |
| Feedback | Accept/reject/abstain/missing kept separate; objective evidence separate | Missing feedback is silently converted to a successful vote |
| Polyglot boundary | One authoritative engine and documented portable types | Three different scoring rules claimed to be identical |

## Minimal proposed fixtures (to be implemented, not supplied as completed router tests)
1. Equal scores yield the documented deterministic tie choice.
2. Expected cost is feasible but the liability bound is not: admission denied.
3. Simultaneous requests cannot reserve the same remaining funds twice.
4. Timeout with unknown usage keeps a pending liability.
5. Repeated settlement is idempotent; conflicting settlement is rejected.
6. Retry or nested option cannot bypass remaining authorization.
7. Check outcomes have explicit pass/fail/unknown control-flow branches.
8. Expensive or inapplicable deterministic tools are not auto-selected.
9. Every choice records eligibility, probability and snapshot version.
10. A rejected/deferrable task remains in the original-workload denominator.

These fixtures validate contracts, not claims of routing quality. Real baseline reproduction and conditional-path evaluation are separate gates with separate reports.
