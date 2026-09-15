# Increment 0 architecture boundary

## Authority and scope

Python is the first authoritative runtime. Future Java and TypeScript components
begin as clients; they do not maintain independent ledgers or scoring behavior.
The six core reference repositories and later architecture references are never
imported by the product package. An upstream adapter may be added only after its
provenance, license, isolated environment, and behavior have been reviewed.

Increment 0 deliberately contains no operational API. Empty modules reserve the
reviewed responsibility boundaries without inventing request schemas or behavior
that belongs to later increments.

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
| `contracts.money` | Exact fixed-unit money and portable decimal strings | Increment 1 |
| `contracts.identifiers` | Immutable request/decision/attempt identities | Increment 1 |
| `contracts.decisions` | Eligibility, selection probability, and versions | Increment 1 |
| `contracts.options` | Bounded conditional option definitions | Increment 3 |
| `contracts.events` | Decision, authorization, execution, and usage events | Increment 1 |
| `contracts.feedback` | Separate preference and objective observations | Increment 1 |
| `core.ledger` | Durable reservation and settlement state | Increment 2 |
| `core.governor` | Upper-liability admission and authorization | Increment 2 |
| `core.graph` | Validation of bounded conditional graphs | Increment 3 |
| `core.executor` | Authorized graph execution and attempt tracing | Increment 4 |
| `core.journal` | Append-only audit records | Increment 5 |
| `policies.fixed` | Fixed-option selection control | Increment 6 |
| `policies.task_rule` | Deterministic task-rule control | Increment 6 |
| `policies.random_mixture` | Seeded logged-propensity control | Increment 6 |
| `adapters` | Reviewed upstream/provider translations | Increment 7 or later |
| `testing` | Fake providers, checkers, and common fixtures | Increment 2 onward |

## Non-goals

This scaffold provides no strict-budget guarantee by itself. It performs no model
calls, retries, embedding, retrieval, verification, deserialization, dataset
access, or benchmark evaluation. In particular, it contains no WISERouter or
Iceberg acquisition algorithm. Those claims require their later acceptance gates.
