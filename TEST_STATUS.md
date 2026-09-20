# Validation record

Date: 20 September 2026.

Required product command executed:
`PYTHONPATH=src python -m unittest discover -s tests/product -t . -v`

Result: all 141 product tests passed. The former PR 3 identical-retry expected
failure is now a passing durable replay regression, and the former PR 1
financial-truth expected failures remain ordinary passing regressions.
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

Focused PR 1 command executed:
`PYTHONPATH=src python -m unittest tests.product.test_known_regressions tests.product.test_increment_two_budget tests.product.test_increment_four_executor -v`

Result: all 23 financial-truth, ledger, and executor tests passed.

Focused PR 2 command executed:
`PYTHONPATH=src python -m unittest tests.product.test_pr_two_workflows tests.product.test_increment_three_graph tests.product.test_increment_four_executor -v`

Result: all 22 workflow, graph, and executor tests passed. The workflow fixtures
cover draft/check/repair reference binding, explicit repaired-answer selection,
pre-authorization artifact failures, and typed timeout/exception deferral with
unknown usage retained as outstanding liability.

Focused PR 3 command executed:
`PYTHONPATH=src python -m unittest tests.product.test_pr_three_recovery tests.product.test_route_retry_contract tests.product.test_increment_eight_router -v`

Result: all 13 ownership, replay, recovery, and router tests passed, including
concurrent duplicate ownership, conflict-before-spend, restart replay, ledger
outbox, and crash-with-uncertain-liability fixtures.

Focused PR 4 command executed:
`PYTHONPATH=src python -m unittest tests.product.test_pr_four_boundaries tests.product.test_increment_seven_adapters tests.product.test_increment_four_executor -v`

Result: all 27 reviewed-boundary, adapter, and executor tests passed. Fixtures cover
resource substitution, exact tariff caps, retries, timeout, cancellation, malformed
responses, delayed billing, over-bound invoices, and local child-process deadline
termination. The child-process boundary is not claimed as filesystem/network
isolation for adversarial tools.

Focused PR 5 command executed:
`PYTHONPATH=src python -m unittest tests.product.test_pr_five_controls tests.product.test_increment_six_policies -v`

Result: all 20 exact-mixture, task-feature, workload-rule, and policy contract tests
passed, including high-precision rejection, reduced draw thresholds, exact logged
probabilities, deterministic replay, and heterogeneous task routing.

No claim of supported behavior for every provider or operating system is made. The
product CI matrix declares Python 3.10–3.13; that hosted matrix was added but was
not executed inside this container. The commands above ran on Python 3.14.4 in the
provided Linux environment. Windows usage is documented but not independently
exercised here.
