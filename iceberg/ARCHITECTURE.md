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
adapters, Increment 5 implements a durable append-only audit journal, and Increment
6 implements three offline control policies, Increment 7 implements the
provider-independent single-attempt adapter boundary, Increment 8 implements
selection-to-execution orchestration, and Increment 9 implements exact offline
coverage and observation accounting. Real provider transports and the Iceberg
acquisition policy remain deferred to separately reviewed increments.

## Dependency direction

```text
                       contracts
                 /       |       |       \
              core   policies  adapters  evaluation
                 \       |       |       /
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
6. `evaluation` may import only contracts. It accounts for supplied observations;
   it cannot execute options, infer missing outcomes, or mutate runtime state.

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
| `core.router` | Policy/audit/executor orchestration | Increment 8 — implemented |
| `policies.fixed` | Fixed-option selection control | Increment 6 — implemented |
| `policies.task_rule` | Deterministic task-rule control | Increment 6 — implemented |
| `policies.random_mixture` | Seeded logged-propensity control | Increment 6 — implemented |
| `contracts.adapters` | Provider-independent attempt/result interface | Increment 7 — implemented |
| `adapters` | Single-attempt boundary; reviewed provider translations | Increment 7 boundary implemented; provider transports deferred |
| `evaluation` | Exact coverage/cost/feedback observation accounting | Increment 9 — implemented |
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

Increment 6 policies are pure selectors over a supplied candidate snapshot. They
cannot import the governor or executor, and therefore cannot authorize spending.
The random-mixture control samples a configured finite-decimal distribution without
binary floating point and logs the probability of the realized selection or
aggregate deferral. It is a control baseline, not an adaptive Iceberg policy.

Increment 7 moves the operation context, normalized result, and structural adapter
protocol into the portable contract layer. Its `SingleAttemptAdapter` validates the
operation kind and version and calls an injected transport once without adding
retries, fallbacks, pricing inference, or zero-usage defaults. It cannot detect retries
hidden inside the injected SDK or gateway; each real transport still requires
provider-specific review and an enforceable liability analysis.

Increment 8 accepts a policy through the contract protocol, requires executable
options to exactly match the immutable candidate snapshot, checks each eligible
candidate's declared upper liability against the validated graph bound, persists
the decision before execution, and records the realized trace afterward. It does
not make policy, journal, ledger, and provider work one atomic transaction. A
duplicate decision fails closed before another execution; crash recovery across
these boundaries remains deferred.

Increment 9 keeps every original-workload row in the reporting denominator, stores
rates as exact integer fractions, totals only known fixed-unit cost, and separately
counts unresolved-cost attempts. User votes, objective results, and checker results
remain separate channels. Executed traces and synthetic tables cannot be aggregated
together. This is accounting infrastructure, not baseline parity or quality evidence.
