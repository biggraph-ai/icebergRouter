# Repository study note: routellm

Repository URL: https://github.com/lm-sys/RouteLLM.git
Pinned SHA: 02d02f10ab10c930604b82a506b76af337b2982c (enclosing snapshot; upstream SHA unknown)
Reviewed files/symbols/line ranges: `routellm/controller.py:Controller` (41–170); `routellm/routers/routers.py:Router` (32–45), router implementations (51–253); `routellm/calibrate_threshold.py` (50–58)
Paper or upstream documentation: root README inspected; claims below use code unless labeled documented
Code / dataset / checkpoint license status: see reuse/open questions

## Observed responsibility

Strong-versus-weak selection. `score >= threshold` chooses strong; calibration selects a score quantile for a desired strong-call percentage. Controller then delegates the selected call to LiteLLM.

## Call-chain trace

messages (last turn only) → router score → threshold → model name → LiteLLM completion → response. Some router constructors download checkpoints/datasets; similarity-weighted scoring calls an embedding API.

## Inputs, outputs and state

See `source-map.md` for the precise schemas and symbol evidence. Mutable model/config/cache state remains upstream-specific; Iceberg adapters must snapshot versions rather than expose live objects.

## Budget and feedback assumptions

Defaults cite Arena human-preference and GPT-4-judge battles. This is preference/judge evidence, not objective correctness. Strong-call share is neither expected dollar budget nor a liability bound. Gateway retries/costs are not recorded by the pure route result.

## Reuse decision

Isolated decision adapter. Iceberg owns option eligibility, execution authorization, attempt/retry trace, exact cost, and objective/user feedback channels. Apache-2.0 root text observed; artifacts retain separate terms.

## Minimal test proposal

After isolated pinned dependencies: invoke `Router.route` with a stub scorer at `t-ε`, `t`, and `t+ε`; no provider/data/network/secret; $0. Expect weak, strong, strong. This tests branching only.

## Executed evidence

NOT RUN. On 2026-09-15 this pass only read source in the supplied Linux workspace. No dependencies were installed; no upstream script, model, dataset, checkpoint, service, network request, or paid call was executed.

## Open questions

Original upstream SHA/artifact hashes unknown; constructor network side effects; calibration dataset availability; LiteLLM retry/fallback behavior.
