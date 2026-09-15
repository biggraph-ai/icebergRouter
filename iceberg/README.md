# IcebergRouter product workspace

This directory is the Iceberg-owned implementation workspace. The top-level
reference repositories remain evidence and are not runtime dependencies.

## Current status: Increment 5

Increment 0 established package ownership and dependency boundaries. Increment 1
implemented portable contracts. Increment 2 added the SQLite liability ledger and
budget governor. Increment 3 added bounded-option definitions and static graph
validation. Increment 4 executes validated graphs through injected adapters,
authorizes every physical attempt, records realized branches, and reconciles known
or pending usage. It still does **not** include a real provider adapter, reproduce
an upstream baseline, select a routing policy, or implement the Iceberg acquisition
policy. Increment 5 adds a durable, immutable SQLite audit journal with atomic
batches, idempotent replay, explicit correction links, and hash-chain verification.
It does not make ledger and journal writes one distributed transaction, and its
hash chain provides tamper evidence rather than external authenticity.

The authoritative Python package lives under `src/iceberg_router`. Its layers are:

- `contracts`: portable values and records; standard-library only;
- `core`: graph execution, accounting, and journaling; may depend on contracts;
- `policies`: pure selection mechanisms; may depend on contracts but cannot spend;
- `adapters`: translations at provider/upstream boundaries; no policy decisions;
- `testing`: Iceberg-owned deterministic fakes and fixtures, never benchmark proof.

Detailed import rules and deferred work are recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Local validation

No installation is necessary for the Increment 0 through Increment 5 checks:

```sh
python -m unittest discover -s tests -v
```

The tests add `src/` to their import path. Structural tests verify package layout
and dependency direction; contract tests cover strict validation, immutable values,
checked arithmetic, explicit unknown states, and JSON round trips. Passing them
Increment 2 tests exercise the ledger against temporary local SQLite databases.
Increment 3 tests validate graph structure and bounds. Increment 4 runs guarded
conditional traces against deterministic scripted adapters. Increment 5 tests
exercise concurrent journal writers, restart, idempotency, corrections, immutable
rows, canonical payloads, and tamper detection. Passing them does not validate an
external provider or routing policy.
