# Source map (reconnaissance only)

Status: 2026-09-15. All six source trees are snapshots in this repository at
containing commit `02d02f10ab10c930604b82a506b76af337b2982c`. They contain no
nested Git metadata or provenance lock, so their original upstream commits are
**unknown**. The containing commit is exact evidence for the reviewed bytes, but
must not be represented as an upstream SHA. No implementation was executed.

| Responsibility | Snapshot file and symbol/lines | Evidence | Iceberg boundary |
|---|---|---|---|
| Independent model-result record | `LLMRouterBench/baselines/schema.py:BaselineRecord` (13–98) | **Inspected:** one dataset/split/model/index record stores prompt, one output, score, token counts, and float USD cost. | Import as historical single-call observations; never synthesize a conditional trace. Convert money only with an explicit tariff/rounding provenance rule. |
| Aggregate and hindsight oracle | `LLMRouterBench/baselines/aggregators.py:BaselineAggregator._compute_stats_for_group` (48–101), `_compute_oracle_stats` (103–134), `_compute_oracle_cost_by_dataset` (136–180+) | **Inspected:** sums recorded float costs; oracle combines independent model records by record index and uses hindsight correctness. | Evaluation reference only. The oracle is not a deployable policy or realized workflow. |
| Weak/strong threshold routing | `RouteLLM/routellm/routers/routers.py:Router.route` (32–45); `routellm/controller.py:Controller._get_routed_model_for_completion` (105–115), `completion` (139–170) | **Inspected:** `score >= threshold` selects strong; only the last message content is scored, then LiteLLM executes the selected model. | Adapt the pure decision boundary; keep execution and budget admission external. |
| Threshold calibration | `RouteLLM/routellm/calibrate_threshold.py` main calibration branch (50–58) | **Inspected:** threshold is the `1 - strong_model_pct` quantile of stored router scores. | It targets a fraction of strong calls, not a per-request money bound. |
| RouteLLM feedback meaning | `RouteLLM/routellm/controller.py:GPT_4_AUGMENTED_CONFIG` (12–28); `routers.py:Router.calculate_strong_win_rate` (32–45) | **Inspected:** defaults name Arena human-preference and GPT-4-judge battle data; the interface calls its scalar a conventional strong-model win rate. | Preserve as preference/judge-derived score, not objective correctness or calibrated success without separate evidence. |
| Sequential cascade planning | `cascade-routing/src/selection/cascade_router.py:CascadeRouter.predict` (65–85), `_predict_model` (87–193), `select_answer` (236–244) | **Inspected:** `None` marks an unrun model; the search scores supermodels by predicted quality minus lambda times summed predicted cost; it may stop by returning `None`, and final answer selection uses predicted quality among available answers. | Reproduce as an isolated table-driven policy; executor must emit actual branch/attempt events. Note the apparent double-append in `select_answer` when no answers exist (242–243) for testing, not silent repair. |
| Cascade budget tuning | `cascade-routing/src/selection/cascade_router.py:CascadeRouter.fit` (196–234); `lambda_strategy.py:ConstantStrategy.compute_lambdas` (44–87) | **Inspected:** fits lambdas to `max_expected_cost` and mixes cheap/expensive tie policies using `gamma`. | Expected-cost comparator only; add a separately named common guard for pathwise liability. |
| Cascade cost/feedback models | `cascade-routing/src/selection/cost_computer.py:GroundTruthCostComputer` (20–82); `quality_computer.py:BaseQualityComputer` (9–124) | **Inspected:** prediction changes with which answer cells are non-`None`; fitting accepts full response tables/measures and learns before/after-run statistics. | Historical counterfactual tables are training/evaluation inputs, not evidence that all branches ran in one deployment trace. |
| Joint model/effort scoring | `R2-Router/r2_router/router.py:R2Router.route` (248–325) | **Inspected:** enumerates model/budget pairs, predicts quality, estimates float USD from estimated input and predicted/budgeted output tokens, and maximizes `(1-lambda)*quality-lambda*cost`. | Pure selector adapter only; predicted cost remains distinct from admission liability. |
| R2 execution semantics | `R2-Router/r2_router/router.py:R2Router.generate` (329–402) | **Inspected:** a finite budget is only a system-prompt instruction; the request payload has no output-token cap; absent usage fields become zero. | Do not call this an enforced budget. Iceberg must supply enforceable caps and represent missing usage as pending. |
| R2 checkpoint loading | `R2-Router/r2_router/router.py:R2Router.from_pretrained` (80–139) | **Inspected:** loads `.joblib` predictors, optionally after a Hugging Face download. | Never deserialize during reconnaissance; require artifact hash, provenance, license, and isolated review. |
| Common router abstraction | `LLMRouter/llmrouter/models/meta_router.py:MetaRouter` (11–109); `custom_routers/randomrouter/router.py:RandomRouter` (19–136) | **Inspected:** subclasses implement single/batch routing and return selected model metadata; the random example reads YAML and uses NumPy choice. | Map only decision output into Iceberg records; do not adopt the zoo or its runtime as budget authority. |
| Evaluation abstraction | `LLMRouter/llmrouter/evaluation/batch_evaluator.py:evaluate_batch` (approximately 152–210) | **Inspected:** metric dispatch mutates/copies result records and converts evaluator exceptions into score `0.0` plus an error. | Preserve evaluator error separately from objective failure; choose explicit policy for aggregation. |
| Gateway retries/fallbacks | `litellm/litellm/router.py:Router.__init__` (704–1028); `router_utils/get_retry_from_policy.py:get_num_retries_from_retry_policy` (46–59) | **Inspected:** retry count defaults through LiteLLM/OpenAI settings; fallbacks, context-window fallbacks, and content-policy fallbacks are configurable; exception-specific retry policy exists. | Disable them or intercept and separately authorize/log every attempt. |
| Gateway reservation | `litellm/litellm/proxy/spend_tracking/budget_reservation.py:reserve_budget_for_request` (201–300), `estimate_request_max_cost` (1080+) | **Inspected:** uses float estimates and counters; unknown/nonpositive estimates skip reservation, unavailable counter writes may continue unless fail-closed, and non-strict overage can resize a reservation. | Useful transport seam, not the Iceberg invariant. Iceberg requires exact money, complete bounds, atomic holds, and fail-closed admission. |
| WISERouter workload allocation | `2607.23765v1.pdf`, §§3.1–4.3, Algorithms 1–2 | **Documented (paper v1):** constrained contextual bandit; query embedding is discretized into clusters; selected action alone reveals reward and normalized token-price cost; ALP allocates remaining expected budget; offline uses historical statistics, online uses epsilon-first exploration. | Implement only as a named paper reproduction after equations are transcribed/reviewed; distinguish WR+Guard and WR-Path adaptations. |

## Repository and license boundaries

| Folder | Notice observed | Boundary |
|---|---|---|
| `LLMRouterBench/` | No root LICENSE found; embedded baselines have their own notices. | Reference/schema study only pending code and dataset terms. |
| `RouteLLM/` | Root Apache-2.0 text. | Adapter/reproduction candidate; model, Hugging Face dataset, and checkpoint terms remain separate. |
| `cascade-routing/` | Root Apache-2.0 text. | Isolated reproduction candidate; datasets/models remain separate. |
| `R2-Router/` | No root code LICENSE; artifact note disclaims complete upstream licensing coverage. | Reference only pending code/checkpoint/data rights. |
| `LLMRouter/` | Root MIT text. | Minimal adapter candidate; audit bundled datasets and third-party components separately. |
| `litellm/` | Root license says non-enterprise code is MIT; `enterprise/` has a restrictive separate license. | Use only reviewed non-enterprise adapter surfaces; do not copy enterprise code. |

The other top-level folders (`GraphPlanner`, `semantic-router`, `gateway`,
`langchain4j`, and `spring-ai`) are later/alternative references, not part of the
six-core pass prescribed by `STUDY_ORDER.md`; no implementation claims about them
are made here.
