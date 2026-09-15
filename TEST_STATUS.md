# Validation record

Date: 15 September 2026.

Command executed: `python -m unittest discover -s tests -v`

Result: 30 tests passed. Ten acquisition tests include real operations against temporary local Git repositories: sparse source checkout, commit pinning, no automatic update, fetching a locked commit into a new destination, refusing unmanaged/modified directories, plus manifest validation, exclusions, exact path escaping, atomic JSON writes and dry-run behavior. Four Increment 0 structural tests verify that the Iceberg-owned modules are importable, observe the declared dependency direction, have no third-party runtime dependencies, and remain separate from the reference directories. Sixteen Increment 1 contract tests cover checked nanodollar arithmetic, canonical decimal-string JSON, typed immutable identifiers, explicit unknown estimates and usage, decision consistency, attempt/authorization pairing, canonical UTC timestamps, independent feedback channels, and strict portable-record round trips.

These are downloader, boundary, and value-contract tests, not Iceberg routing,
ledger, provider-execution, or quality tests. The six core source snapshots and WISERouter paper are
available in this workspace, but their original upstream commit identities are not
preserved. Upstream packages were not installed, checkpoint files were not loaded,
upstream tests were not run, and no paper results were reproduced.

No claim of supported behavior for every provider, runtime or operating system is made. The downloader uses Python's standard library and Git; its local tests ran in the provided Linux environment. Windows usage is documented but not independently exercised here.
