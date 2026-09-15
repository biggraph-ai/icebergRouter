# IcebergRouter architecture boundary

## Authority and scope

Python is the first authoritative runtime. Future Java and TypeScript components
begin as clients; they do not maintain independent ledgers or scoring behavior.
The six core reference repositories and later architecture references are never
imported by the product package. An upstream adapter may be added only after its
provenance, license, isolated environment, and behavior have been reviewed.

Increment 0 established the module boundaries, Increment 1 implemented portable
contracts, Increment 2 implemented the single-host SQLite ledger and admission
governor, Increment 3 implemented bounded conditional option definitions and
static validation, Increment 4 implements guarded graph execution against injected
adapters, and Increment 5 implements a durable append-only audit journal. Real
provider transport and selection remain deferred to their separately reviewed
increments.

## Dependency direction

```text
                 contracts
                /    |    \
            core  policies  adapters
              \       |       /
                    testing
```

The diagram indicates allowed knowledge, not runtime control:

1. `contracts` uses only the Python standard library. It cannot import another
   Iceberg layer, a provider SDK, or a reference repository.
2. `core` may import `contracts`. It cannot import policies, adapters, testing, or
   a reference repository.
3. `policies` may import `contracts`. A policy estimates and selects; it cannot
   import the governor/executor in `core` or invoke an adapter.
4. `adapters` may import `contracts`. It cannot select a policy, create budget
   authorization, or import a reference tree directly.
5. `testing` may import any Iceberg layer to provide deterministic fakes and
   contract fixtures. Production layers cannot import `testing`.

Cross-layer interaction will use contracts defined in later, separately reviewed
increments. These rules keep selection, admission, execution, and provider
transport independently testable.

## Reserved modules and deferred behavior

| Module | Reserved responsibility | First behavior-owning increment |
|---|---|---|
| `contracts.money` | Exact fixed-unit money and portable decimal strings | Increment 1 — implemented |
| `contracts.identifiers` | Immutable request/decision/attempt identities | Increment 1 — implemented |
| `contracts.decisions` | Eligibility, selection probability, and versions | Increment 1 — implemented |
| `contracts.options` | Bounded conditional option definitions | Increment 3 — implemented |
| `contracts.events` | Execution and usage events with attempt identities | Increment 1 — implemented |
| `contracts.feedback` | Separate preference, objective, and checker observations | Increment 1 — implemented |
| `core.ledger` | Durable reservation and settlement state | Increment 2 — implemented |
| `core.governor` | Upper-liability admission and authorization | Increment 2 — implemented |
| `core.graph` | Validation of bounded conditional graphs | Increment 3 — implemented |
| `core.executor` | Authorized graph execution and attempt tracing | Increment 4 — implemented |
| `core.journal` | Append-only hash-chained audit records | Increment 5 — implemented |
| `policies.fixed` | Fixed-option selection control | Increment 6 |
| `policies.task_rule` | Deterministic task-rule control | Increment 6 |
| `policies.random_mixture` | Seeded logged-propensity control | Increment 6 |
| `adapters` | Reviewed upstream/provider translations | Increment 7 or later |
| `testing` | Fake providers, checkers, and common fixtures | Increment 2 onward — scripted adapters implemented |

## Non-goals

The executor enforces local attempt and accounting rules against injected adapters,
but no external provider bound, cancellation, or timeout behavior has been
validated. It performs no real model call, embedding, retrieval, deserialization,
dataset access, or benchmark evaluation. It contains no WISERouter or Iceberg
acquisition algorithm. Those claims require their later acceptance gates.

The Increment 5 journal serializes concurrent writers, rejects row mutation, and
detects in-place changes by replaying its SHA-256 hash chain. A hash chain is not a
signature or external transparency log: an actor with database and schema control
can rewrite the chain. Journal writes are not transactionally coupled to ledger
mutations or provider calls, so the ledger remains authoritative and crash-gap
reconciliation is still required.
