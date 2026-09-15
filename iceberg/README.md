# IcebergRouter product workspace

This directory is the Iceberg-owned implementation workspace. The top-level
reference repositories remain evidence and are not runtime dependencies.

## Current status: Increment 1

Increment 0 established package ownership and dependency boundaries. Increment 1
implements the portable contract layer: checked fixed-unit money, immutable typed
identifiers, routing decision records, execution/usage events, and independent
feedback observations. It still does **not** implement a router, ledger, provider
call, upstream reproduction, or the Iceberg acquisition policy.

The authoritative Python package lives under `src/iceberg_router`. Its layers are:

- `contracts`: portable values and records; standard-library only;
- `core`: graph execution, accounting, and journaling; may depend on contracts;
- `policies`: pure selection mechanisms; may depend on contracts but cannot spend;
- `adapters`: translations at provider/upstream boundaries; no policy decisions;
- `testing`: Iceberg-owned deterministic fakes and fixtures, never benchmark proof.

Detailed import rules and deferred work are recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Local validation

No installation is necessary for the Increment 0 and Increment 1 checks:

```sh
python -m unittest discover -s tests -v
```

The tests add `src/` to their import path. Structural tests verify package layout
and dependency direction; contract tests cover strict validation, immutable values,
checked arithmetic, explicit unknown states, and JSON round trips. Passing them
does not validate a ledger, executor, provider, or routing policy.
