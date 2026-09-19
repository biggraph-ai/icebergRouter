# Validation record

Date: 19 September 2026.

Required product command executed:
`PYTHONPATH=src python -m unittest discover -s tests/product -t . -v`

Result: 112 product tests ran successfully: 109 passed and three documented expected
failures record two PR 1 financial-truth defects and the PR 3 public identical-retry
contract. Expected failures are owner-tagged requirements, not accepted behavior.
They are separate from, and do not weaken, the passing current-behavior and
append-only/conflicting-identity tests. The complete product suite produced the
same result from a temporary clean product-only tree with no reference repositories.

Optional study command executed:
`python -m unittest discover -s tests/study -t . -v`

Result: 12 study/downloader tests passed in this study checkout. The same command
ran from a temporary tree without reference repositories: 11 passed and the
optional reference-presence check skipped, as designed.

These are boundary, contract, local-ledger, static-graph, scripted executor,
journal, offline control-policy, injected-transport boundary, orchestration,
evaluation-accounting, and optional downloader/study tests—not real provider integration,
adaptive routing, feedback learning, baseline parity, or quality tests. The six core source snapshots and WISERouter
paper are available in this workspace, but their original upstream commit
identities are not preserved. Upstream packages were not installed, checkpoint
files were not loaded, upstream tests were not run, and no paper results were
reproduced.

No claim of supported behavior for every provider or operating system is made. The
product CI matrix declares Python 3.10–3.13; that hosted matrix was added but was
not executed inside this container. The commands above ran on Python 3.14.4 in the
provided Linux environment. Windows usage is documented but not independently
exercised here.
