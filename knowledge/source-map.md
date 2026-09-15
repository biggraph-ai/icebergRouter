# Source map

Status date: 2026-09-15. `NOT INSPECTED` means the upstream source could not be
retrieved; a workspace document naming a path is not implementation evidence.

| Concept | Evidence target | Commit | File/symbol evidence | Status |
|---|---|---|---|---|
| Offline outcome schema/evaluation | LLMRouterBench | unavailable | `README.md`, `baselines/`, `evaluation/`, `config/` (workspace targets only) | NOT INSPECTED |
| Score-to-model threshold | RouteLLM | unavailable | `routellm/controller.py`, routers, `calibrate_threshold.py` (targets only) | NOT INSPECTED |
| Stop/continue/final-answer cascade | Cascade Routing | unavailable | `cascade_router.py`, `baseline_cascader.py`, quality/cost computers, lambda strategy (targets only) | NOT INSPECTED |
| Joint model/output-budget choice | R2-Router | unavailable | `r2_router/router.py`, config, `route.py`, reproduction files (targets only) | NOT INSPECTED |
| Common router/experiment interface | LLMRouter | unavailable | `llmrouter/`, `custom_routers/`, configs/tests (targets only) | NOT INSPECTED |
| Provider normalization/retry/usage | LiteLLM | unavailable | `litellm/`, `gateway/`, tests, architecture/license files (targets only) | NOT INSPECTED |
| Contextual workload allocation | WISERouter paper v1 | n/a | sections 3–4, Algorithms 1–2 and appendices (targets only) | NOT INSPECTED |

## Local implementation evidence

The only inspected executable is this workspace's acquisition tool at commit
`f150f4201dc4f5c935fa75585d615d2476c20191`:

- `fetch_references.py:validate_entry` validates repository identifiers, HTTPS
  GitHub clone URLs, optional full SHAs, and study roots.
- `fetch_references.py:select_paths` filters Git trees to reviewable source/text
  files and notices while excluding instruction, data, weight, and build paths.
- `fetch_references.py:git` supplies isolated Git configuration.
- `fetch_references.py:prepare` pins/verifies commits and creates sparse checkouts.
- `fetch_references.py:atomic_json` replaces the lock file atomically.

These symbols say nothing about the behavior of any routing baseline.
