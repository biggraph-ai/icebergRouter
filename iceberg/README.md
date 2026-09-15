# IcebergRouter product workspace

This directory is the Iceberg-owned implementation workspace. The top-level
reference repositories remain evidence and are not runtime dependencies.

## Increment 0 status

Increment 0 establishes package ownership and dependency boundaries only. It does
**not** implement a router, ledger, provider call, upstream reproduction, or the
Iceberg acquisition policy.

The authoritative Python package lives under `src/iceberg_router`. Its layers are:

- `contracts`: portable values and records; standard-library only;
- `core`: graph execution, accounting, and journaling; may depend on contracts;
- `policies`: pure selection mechanisms; may depend on contracts but cannot spend;
- `adapters`: translations at provider/upstream boundaries; no policy decisions;
- `testing`: Iceberg-owned deterministic fakes and fixtures, never benchmark proof.

Detailed import rules and deferred work are recorded in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Local validation

No installation is necessary for the Increment 0 checks:

```sh
python -m unittest discover -s tests -v
```

The structural tests add `src/` to their import path and verify the package layout
and dependency direction. Passing them proves only that the scaffold respects the
declared boundaries.
