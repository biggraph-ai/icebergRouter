# Study order and required outputs

The order below is our engineering recommendation. Source facts come from the primary URLs in `repo_manifest.json` and `REFERENCES.md`; assignments and acceptance tests are proposed work, not results already reproduced.

## 0. Requirements and WISERouter first
Read the audited design and the WISERouter paper before interpreting a collection of code as Iceberg's invention. Sections 3–4 define contextual workload allocation, embedding clusters, offline estimates and exploration before allocation. Its stated optimization uses expected cost. The author-linked code location was not verified in this search. [S1]

Output: `knowledge/wiserouter-spec.md`, including assumptions, paper section/algorithm mapping and unresolved details. If implementing from the paper, call it a paper-based reproduction. Keep `wr-paper-reproduction`, `wr-plus-common-guard`, and `wr-path-adaptation` distinct. Use tiny deterministic problems to check distributions, null actions, budget updates and solver results before any claim about paper reproduction.

## 1. The six core source repositories

### 1. llmrouterbench
Repository: `https://github.com/ynulihao/LLMRouterBench.git`

Start with: `README.md`, `baselines/`, `evaluation/`, `config/`.

Offline dataset and evaluation reference; not synthetic evidence for unexecuted conditional paths.

Study question: Can a row be interpreted as an independent model outcome, or a conditional workflow? How are score and cost populated? Which dataset artifacts are outside Git?

Required output: Produce a schema map and split plan. On a reviewed tiny fixture, compute fixed-model and task-rule baselines. Label synthetic fixtures as synthetic; do not call them a benchmark result.

License/provenance note: Not confirmed in this review. Inspect pinned code and separate dataset terms before copying or redistribution.

### 2. routellm
Repository: `https://github.com/lm-sys/RouteLLM.git`

Start with: `README.md`, `routellm/controller.py`, `routellm/routers/`, `routellm/calibrate_threshold.py`, `routellm/evals/`, `routellm/tests/`.

Reference model-selection baseline and threshold calibration.

Study question: Trace request → router score → calibrated threshold → model choice. Separate preference prediction from factual correctness.

Required output: Produce a call-chain note and an offline threshold-boundary test with mocked inference. Then plan one genuine upstream smoke test; do not claim the mock reproduces trained router quality.

License/provenance note: Repository page identifies Apache-2.0; inspect pinned notices and artifact licenses.

### 3. cascade-routing
Repository: `https://github.com/eth-sri/cascade-routing.git`

Start with: `README.md`, `src/selection/cascade_router.py`, `src/selection/baseline_cascader.py`, `src/selection/quality_computer.py`, `src/selection/cost_computer.py`, `src/selection/lambda_strategy.py`.

Sequential decision baseline: stop, call another model, select a final answer.

Study question: Trace missing responses, quality/cost predictions, stop decisions and final answer selection. Identify what training information the method assumes.

Required output: Construct a small response table with stop, continue and exhausted-budget cases. Identify exactly which upstream methods can run without API calls. Do not run its full reproduction script as an onboarding step.

License/provenance note: Repository page identifies Apache-2.0; inspect pinned notices.

### 4. r2-router
Repository: `https://github.com/UCF-ML-Research/R2-Router.git`

Start with: `README.md`, `r2_router/router.py`, `r2_router/config.json`, `route.py`, `reproduce/`, `DATA_RELEASE.md`.

Joint model and output-budget selection; a required comparison for cost reduction claims.

Study question: Map (model, output budget) to predicted quality/cost. Distinguish estimated tokens, prompted output length, and enforceable billing limits.

Required output: Use a tiny synthetic model-budget grid to test adapter selection. Resolve the README clone-target discrepancy. Document the reviewed checkpoint format before any loading.

License/provenance note: Not confirmed in this review. Inspect pinned code, checkpoint and dataset terms separately.

### 5. llmrouter
Repository: `https://github.com/ulab-uiuc/LLMRouter.git`

Start with: `README.md`, `CUSTOM_ROUTER_SUMMARY.md`, `llmrouter/`, `custom_routers/`, `configs/`, `tests/`.

Common router interfaces, configurable baselines and experiment adapters; do not run its entire algorithm zoo.

Study question: Find the router interface, one simple classifier, configuration loading and evaluation entry point. Map its abstraction to ours rather than adopting every component.

Required output: Produce an adapter skeleton and compare a simple baseline with the shared fixture. Do not implement all supported algorithms.

License/provenance note: Repository page identifies MIT; inspect pinned notices and bundled third-party material.

### 6. litellm
Repository: `https://github.com/BerriAI/litellm.git`

Start with: `README.md`, `ARCHITECTURE.md`, `litellm/`, `gateway/`, `tests/`, `LICENSE`.

Replaceable provider gateway; inspect billing, retries, streaming and failure semantics rather than adopting its guarantees untested.

Study question: Find provider normalization, usage pricing, retries, streaming, budget reservation and failure paths. Read current budget documentation separately. [S7]

Required output: Design a mock-provider integration test covering cancellation, unknown usage, duplicate settlement, stale budget state and retries. All paid attempts must remain visible to the common governor.

License/provenance note: Mixed licensing boundaries; inspect LICENSE and commercial/enterprise areas. No copying approval is implied.

## 2. Baseline integration, not Iceberg yet
Build a minimal adapter harness in a separate product repository. Feed it one common synthetic fixture first. Then prepare an approved real dataset subset with frozen splits. The output must include utility, cost, coverage and a trace per decision. Keep native upstream policy decisions separate from externally blocked/adapted decisions.

Propose `OptionExecutor`, `RoutingPolicy`, `BudgetGovernor`, `OutcomeStore` and `FeedbackStore` contracts. The same option definitions and the same budget governor must be available to each mechanism comparison. A provider failure fallback is not a response-quality escalation unless explicitly defined that way.

## 3. Later architecture references
Read vLLM Semantic Router only when designing integration boundaries: source, configuration and end-to-end tests. Read GraphPlanner when evaluating graph memory or learned workflow construction. Neither is a mandatory runtime for the first finite-option experiment. [S8–S9]

Read PILOT before adding preference-conditioned embeddings and online bandit feedback. Read the recent RLCascadeRouter paper before claiming novelty for adaptive stopping/model choice. These are literature checks, not a requirement to accumulate more repositories. [S13–S14]

## 4. Language adapters after reference semantics
For Java, choose plain HTTP first or inspect LangChain4j; Spring AI is an alternative, not an additional mandatory dependency. For TypeScript, start with an HTTP client and inspect Vercel AI SDK for integration needs. Study the selected request/response and streaming APIs, not all vector stores or UI examples. [S10–S12]

A source-only checkout is not build complete. Install a reviewed pinned package or use a separate full checkout at the locked SHA when reproduction is authorized. Isolate each repo's dependencies.

## 5. Permission to implement the new policy
Proceed only when the acceptance gates in `ACCEPTANCE_GATES.md` have concrete evidence or an explicit documented deferral. Then implement uniform/stratified probe allocation and an equal-option workload allocator first. Add the Iceberg-specific acquisition rule as one named variant. Save graph learning, personalization and router-of-routers claims for measured extensions.
