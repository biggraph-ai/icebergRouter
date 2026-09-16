# Validation record

Date: 16 September 2026.

Command executed: `python -m unittest discover -s tests -v`

Result: 119 tests passed. Ten acquisition tests cover temporary local Git operations; four Increment 0 tests enforce package boundaries; sixteen Increment 1 tests cover portable contracts; fourteen Increment 2 tests cover the local budget authority; eleven Increment 3 tests cover bounded graph contracts and validation; seven Increment 4 tests cover guarded execution; twelve Increment 5 tests cover the audit journal; twelve Increment 6 tests cover control policies; eight Increment 7 tests cover the adapter boundary; seven Increment 8 tests cover orchestration; ten Increment 9 tests cover evaluation accounting; and eight Increment 10 tests cover feedback storage and snapshots.

These are downloader, boundary, contract, local-ledger, static-graph, scripted
executor, journal, offline control-policy, injected-transport boundary, and
orchestration, and evaluation-accounting tests—not real provider integration,
adaptive routing, feedback learning, baseline parity, or quality tests. The six core source snapshots and WISERouter
paper are available in this workspace, but their original upstream commit
identities are not preserved. Upstream packages were not installed, checkpoint
files were not loaded, upstream tests were not run, and no paper results were
reproduced.

No claim of supported behavior for every provider, runtime or operating system is made. The downloader uses Python's standard library and Git; its local tests ran in the provided Linux environment. Windows usage is documented but not independently exercised here.
