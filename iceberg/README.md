# IcebergRouter product workspace

This directory is the Iceberg-owned implementation workspace. The top-level
reference repositories remain evidence and are not runtime dependencies.

## Current status: Increment 7

Increment 0 established package ownership and dependency boundaries. Increment 1
implemented portable contracts. Increment 2 added the SQLite liability ledger and
budget governor. Increment 3 added bounded-option definitions and static graph
validation. Increment 4 executes validated graphs through injected adapters,
authorizes every physical attempt, records realized branches, and reconciles known
or pending usage. It still does **not** include a real provider adapter, reproduce
an upstream baseline, or implement the Iceberg acquisition policy. Increment 5 adds
a durable, immutable SQLite audit journal with atomic
batches, idempotent replay, explicit correction links, and hash-chain verification.
It does not make ledger and journal writes one distributed transaction, and its
hash chain provides tamper evidence rather than external authenticity.
Increment 6 adds pure fixed-option, workload-rule, and seeded random-mixture
controls. These selectors preserve the supplied eligibility and estimate snapshot,
log deterministic or exact finite-decimal propensities, and never authorize spend.
Increment 7 adds a provider-independent operation contract and a single-attempt
adapter wrapper for injected transports. It intentionally ships no provider SDK or
real provider transport and cannot certify that an injected SDK has no hidden
retries.

The authoritative Python package lives under `src/iceberg_router`. Its layers are:

- `contracts`: portable values and records; standard-library only;
- `core`: graph execution, accounting, and journaling; may depend on contracts;
- `policies`: pure selection mechanisms; may depend on contracts but cannot spend;
- `adapters`: translations at provider/upstream boundaries; no policy decisions;
- `testing`: Iceberg-owned deterministic fakes and fixtures, never benchmark proof.

Detailed import rules and deferred work are recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Local validation

No installation is necessary for the Increment 0 through Increment 7 checks:

```sh
python -m unittest discover -s tests -v
```

The tests add `src/` to their import path. Structural tests verify package layout
and dependency direction; contract tests cover strict validation, immutable values,
checked arithmetic, explicit unknown states, and JSON round trips. Increment 2
tests exercise the ledger against temporary local SQLite databases.
Increment 3 tests validate graph structure and bounds. Increment 4 runs guarded
conditional traces against deterministic scripted adapters. Increment 5 tests
exercise concurrent journal writers, restart, idempotency, corrections, immutable
rows, canonical payloads, and tamper detection. Increment 6 tests cover
deterministic selection and deferral, immutable policy configuration, seed replay,
exact mixture propensities, and invalid snapshots. Increment 7 tests cover
authorized attempt identity, known-versus-unknown usage,
operation-kind isolation, exactly one wrapper-level transport invocation, strict
result typing, and exception propagation without adapter-level retry. Passing these
tests does not validate an external provider or an adaptive routing policy.
