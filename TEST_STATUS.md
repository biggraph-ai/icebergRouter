# Validation record

Date: 15 September 2026.

Command executed: `python -m unittest discover -s tests -v`

Result: 44 tests passed. Ten acquisition tests cover temporary local Git operations; four Increment 0 tests enforce package boundaries; sixteen Increment 1 tests cover portable value and event contracts; and fourteen Increment 2 tests exercise atomic SQLite admission, concurrent reservation, retry identity, pending usage across restart, idempotent and conflicting settlement, reconciliation, authorization requirements, and bound-breach shutdown.

These are downloader, boundary, contract, and local-ledger tests, not Iceberg
option-execution, provider-integration, routing, or quality tests. The six core source snapshots and WISERouter paper are
available in this workspace, but their original upstream commit identities are not
preserved. Upstream packages were not installed, checkpoint files were not loaded,
upstream tests were not run, and no paper results were reproduced.

No claim of supported behavior for every provider, runtime or operating system is made. The downloader uses Python's standard library and Git; its local tests ran in the provided Linux environment. Windows usage is documented but not independently exercised here.
