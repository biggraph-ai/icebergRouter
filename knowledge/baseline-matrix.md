# Baseline comparison matrix

`Inspected` means source bytes were read at the containing snapshot commit;
`documented` means the paper/README states it; `tested` is **none** in this pass.

| Baseline | Choice / outcome unit | Cost and budget assumption | Feedback visibility | Trace status | Reuse |
|---|---|---|---|---|---|
| Fixed option | One frozen bounded option | Iceberg expected estimate + common liability guard | Executed outcome only | Real attempt trace | Iceberg-owned control |
| Task rule / random mixture | One eligible option | Same guard and accounts | Executed outcome only; log propensity | Real attempt trace | Iceberg-owned control |
| LLMRouterBench | One independent `(dataset, split, model, index)` output | Float USD recorded per row and summed; no liability bound (**inspected**) | Ground truth/score present in offline record | Not a conditional path | Dataset/evaluator adapter only |
| RouteLLM | Strong or weak model via `score >= threshold` | Calibration controls strong-call percentage, not dollars; no upper-liability admission (**inspected**) | Arena preference and judge battles in defaults; only chosen call executes | One model call, gateway behavior additional | Pure decision adapter |
| Cascade Routing | Next model or stop, then select among observed answers | Optimizes average/expected cost with fitted lambda and randomized tie mixture; no pathwise ceiling (**inspected**) | Training/evaluation accepts response tables; `None` means unrun | Sequential policy can be simulated from table; must execute afresh for real traces | Isolated reproduction |
| R2-Router | `(model, output-budget)` | Float predicted USD; input tokens approximated; finite budget is prompt-only, “unlimited” tokens predicted (**inspected**) | Ridge quality/token predictors loaded from joblib | One selected generation | Selector adapter only; replace execution cap |
| LLMRouter | Algorithm-specific model decision | Common interface does not establish shared budget admission (**inspected**) | Varies by router/dataset | Usually decision record, not compound trace | Minimal interface mapping only |
| WISERouter offline | One model for each clustered query context | Maximizes expected reward under expected workload cost through ALP (**paper documented**) | Historical reward/cost statistics for context-action pairs | Single selected action | Paper-based reproduction |
| WISERouter online | One model per round after epsilon-first exploration | Exploration and exploitation share expected budget (**paper documented**) | Bandit feedback only for selected model | Sequential single-action rounds | Paper-based reproduction |
| WR+Guard | Native WR selection, externally admitted | Expected-cost selection plus Iceberg bound | Chosen feedback only | Full authorized attempt | Separately named adaptation |
| WR-Path+Guard | Frozen compound option as action | Same estimator/governor/options as Iceberg | Real terminal option outcome only | Real conditional option trace | Decisive adapted comparator; no inherited theorem |
| Iceberg probe variants | Random, stratified, then named active acquisition | Probe/check/embedding cost charged; common guard | Only genuinely acquired signals | Full probe and service traces | Future work, not implemented |

## Matched-comparison requirements

All mechanisms receive the same frozen workload visibility, eligibility predicates,
options, tariffs, tool/checker permissions, abstention, and budget governor. Report
total utility over the original workload, served quality, coverage/deferral/failure,
confirmed spend, unresolved holds, latency, and routing/adaptation overhead. Keep
queued-batch and future-blind streaming regimes separate. Native selection, guard
rejection, and fallback are distinct events. No hindsight oracle or independent
stored completion is a deployable conditional workflow.
