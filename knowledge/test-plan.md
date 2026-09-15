# Smallest offline reproduction plan

All commands below are proposals pending source retrieval and review. Use one
isolated environment per upstream repository; freeze the exact SHA and dependencies
before execution. Do not install in this reconnaissance workspace. Synthetic input
tests validate plumbing/branching, not published quality or benchmark results.

| Target | Smallest fixture and expected observation | Required artifacts | Network/secrets/cost |
|---|---|---|---|
| LLMRouterBench | Tiny synthetic schema fixture; hand-check fixed-model and task-rule cost/utility/coverage | Inspected evaluator source only | None / none / $0 |
| RouteLLM | Mock scores below/equal/above threshold; observe exact weak/strong boundary | Inspected controller/router/calibration source and minimal pinned deps | None / none / $0 |
| Cascade Routing | Four-row synthetic response table: stop, continue, missing, exhausted; observe selected calls/answer | Inspected pure selection modules and minimal pinned deps | None / none / $0 |
| R2-Router | Tiny `(model, budget)` quality/cost grid with tie and infeasible pair | Inspected selector/config; no checkpoint | None / none / $0 |
| LLMRouter | One simple router over common synthetic requests; translate decision record | Inspected interface/config/evaluator and minimal pinned deps | None / none / $0 |
| LiteLLM | Local fake provider: success, unknown-usage timeout, cancel, retry; observe attempt/usage events | Inspected mock seam and minimal pinned deps | Loopback only / none / $0 |
| WISERouter | Hand-computed deterministic allocation tables including null, ties, zero budget, seeded draw | Paper-derived local implementation only after specification review | None / none / $0 |

## Common contract fixtures before Iceberg acquisition

1. Equal scores take the documented deterministic tie action and log probability.
2. Expected cost fits but upper liability does not: deny admission.
3. Concurrent reservations cannot spend the same remainder twice.
4. Timeout with unknown usage retains pending liability.
5. Duplicate identical settlement is idempotent; conflicting settlement fails.
6. Retry and nested attempts require unique authorization and accounting identities.
7. Verifier pass/fail/unknown drives explicit, bounded branches.
8. Inapplicable/expensive deterministic tools remain ineligible.
9. Every decision records eligibility, probability, policy and snapshot versions.
10. Deferral remains in the original-workload coverage denominator.
11. Integer-string money round-trips across JSON and rejects floats/overflow.
12. Crash/replay reconstructs the same confirmed and outstanding balances.

## Reproduction record template

For every eventual run capture exact command, date, OS/runtime, isolated environment
hash/lock, source SHA, fixture hash, randomness, network and secret permissions,
expected maximum expense, exit code, stdout/stderr log, output artifacts, and
limitations. Keep `native`, `common-guard`, and other adaptations separately named.
