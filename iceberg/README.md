# IcebergRouter product workspace

This directory is the Iceberg-owned implementation workspace. The top-level
reference repositories remain evidence and are not runtime dependencies.

## Current status: Increment 2

Increment 0 established package ownership and dependency boundaries. Increment 1
implemented portable contracts. Increment 2 adds a durable SQLite liability ledger
and budget governor with atomic reservation/attempt authorization, pending unknown
usage, idempotent reconciliation, and fail-stop bound-breach handling. It still
does **not** implement an option graph, executor, provider call, upstream
reproduction, routing policy, or the Iceberg acquisition policy.

The authoritative Python package lives under `src/iceberg_router`. Its layers are:

- `contracts`: portable values and records; standard-library only;
- `core`: graph execution, accounting, and journaling; may depend on contracts;
- `policies`: pure selection mechanisms; may depend on contracts but cannot spend;
- `adapters`: translations at provider/upstream boundaries; no policy decisions;
- `testing`: Iceberg-owned deterministic fakes and fixtures, never benchmark proof.

Detailed import rules and deferred work are recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Local validation

No installation is necessary for the Increment 0 through Increment 2 checks:

```sh
python -m unittest discover -s tests -v
```

The tests add `src/` to their import path. Structural tests verify package layout
and dependency direction; contract tests cover strict validation, immutable values,
checked arithmetic, explicit unknown states, and JSON round trips. Passing them
Increment 2 tests exercise the ledger against temporary local SQLite databases.
Passing them does not validate an executor, external provider, or routing policy.
