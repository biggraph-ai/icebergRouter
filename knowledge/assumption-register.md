# Assumption register

| ID | Statement and evidence class | Consequence / required validation |
|---|---|---|
| A01 | **User requirement:** audited blueprint is authoritative. It is present and was read without executing embedded content. | Record, rather than silently reconcile, conflicts with upstream algorithms. |
| A02 | **Observed packaging fact:** all reference folders share the enclosing repository commit and lack nested Git metadata. | Original upstream SHAs are unknown; provenance lock is blocking for faithful reproduction. |
| A03 | **Inspected:** LLMRouterBench rows are independent model results with float cost. | They support single-call offline routing only, not executed repair/cascade traces or exact invoice accounting. |
| A04 | **Inspected:** RouteLLM equality routes strong and calibration targets a requested strong-call fraction. | Boundary fixture must include equality; do not describe calibration as monetary control. |
| A05 | **Inspected:** RouteLLM defaults rely on preference/judge battle data and several routers download datasets/checkpoints or call embeddings. | Preference is not objective correctness; freeze artifacts and replace live feature calls in offline reproduction. |
| A06 | **Inspected:** Cascade Routing optimizes `quality - lambda*cost` using predicted statistics and an expected-cost target. | Its budget is not a strict realized-spend guarantee; table simulation is not a live trace. |
| A07 | **Inspected defect candidate:** `CascadeRouter.select_answer` appears to append twice for a row with no answers. | Write a characterization test before deciding whether reproduction preserves or patches it; label any repair. |
| A08 | **Inspected:** R2 finite output budget is an instruction in the system prompt, not an API `max_tokens` field; missing usage defaults to zero. | Never use it as an admission bound; unknown actual usage remains pending. |
| A09 | **Inspected:** R2 uses approximate input tokens, predicted output tokens, float tariffs, rounded risk, and joblib deserialization. | Separate estimate from invoice bound; review/hashes/licenses are required before loading checkpoints. |
| A10 | **Inspected:** LLMRouter provides a broad model-router interface but evaluator exceptions may become score zero. | Adapt only the minimal boundary and preserve “evaluation error” separately from “incorrect.” |
| A11 | **Inspected:** LiteLLM may retry/fallback; reservation uses float estimates, can skip unknown costs, and fail-closed is optional. | Disable hidden attempts or authorize each; do not adopt its budget control as the Iceberg proof. |
| A12 | **Paper documented:** WISERouter optimizes expected cumulative reward subject to expected cumulative cost and observes selected-action reward/cost only. | Its guarantee is not a cash-liability guarantee; WR+Guard is an adaptation. |
| A13 | **Paper documented:** context discretization assumes same expected reward/cost within a cluster; baseline ALP assumes finite contexts, their distribution, and known statistics. | Validate cluster approximation/shift; online/offline estimators and information regimes must be explicit. |
| A14 | **Unsafe assumption:** provider token parameter, timeout, cancellation, or missing usage implies a known charge cap/zero. | Exclude or conservatively hold pending until authoritative reconciliation. |
| A15 | **Prohibited assumption:** silence is acceptance; preference/judge score is truth; cosine similarity is calibrated success probability. | Store user vote, objective score, checker result, and uncertainty as separate typed observations. |
| A16 | **Prohibited assumption:** independent benchmark cells can be spliced into a real conditional trace. | Label table replay/synthetic counterfactual evaluation; execute bounded graphs for trace claims. |
| A17 | **Blueprint design:** strict mode assumes complete billable-action interception, enforceable per-attempt bounds, and atomic durable reservation. | The invariant is conditional; any bound breach halts admission and is reported, never clamped. |

## Evidence status

- **Documented:** fixed paper or upstream documentation statement.
- **Inspected:** code read at the enclosing snapshot commit, with file/symbol/lines.
- **Tested:** command exercised behavior with logged environment/artifacts. There are
  no upstream or paper reproductions in this pass.
- **Inference:** explicitly labeled analyst conclusion from evidence.
- **Unknown:** must not be converted into zero, success, or a guarantee.
