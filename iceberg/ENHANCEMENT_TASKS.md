# IcebergRouter enhancement backlog

Status: implementation plan, not completed behavior. Prepared 19 September 2026
from the requested PR 0–8 decision and a static inspection of the current branch.

## Evidence and interpretation

Evidence labels used below:

- **Observed** means the current branch contains the cited behavior.
- **Supplied** means the behavior or requirement comes from the review decision in
  the task request; it has not been independently reproduced here.
- **Proposed** means work or an acceptance condition, not a feature claim.

The current package contains the 27 Python source modules frozen by
`tests/test_increment_zero.py`. The supplied statement that all 27 files match a
prior review manifest is recorded but not independently re-verified: neither
`REANALYSIS.md` nor `results/` is present in this checkout. Add those artifacts or
their immutable hashes before treating them as repository evidence.

Existing behavioral tests remain requirements. A failing regression may be marked
as an expected failure only in the PR that first introduces it, with an owner and
removal condition. Do not delete or weaken an acceptance test to make a gate pass.

## Sequence and release boundary

```text
PR 0 (independent tests)
  ├── PR 1 (financial truth) ──┐
  ├── PR 2 (data flow) ────────┼── PR 3 (durable ownership/recovery)
  ├── PR 5 (controls)          └── PR 4 (reviewed bounded adapter)
  └── PR 6 (experiment isolation/accounting)

PRs 0–6 complete the first runtime milestone.
PR 7 reproduces baselines only after the applicable evidence gates pass.
PR 8 tests the Iceberg acquisition hypothesis only after PR 7 is stable.
```

PRs 7–8 are blocked by the provenance, artifact, license, and baseline-parity
items in `knowledge/blocked-items.md`. Do not begin a transformer router, dynamic
topology, distributed ledger, native Java/TypeScript policy engine, or multi-host
financial authority in this sequence.

---

## PR 0 — independently testable product checkout

**Goal:** make product validation independent of the study-kit reference trees.

**Observed gaps**

- `tests/test_increment_zero.py` requires six capitalized reference directories at
  repository root.
- `fetch_references.py` defaults to `references/repos/<manifest-id>`, where IDs are
  lowercase and include names such as `r2-router`.
- downloader/study tests and product tests share one discovery directory.
- no repository-owned CI workflow is present.
- `pyproject.toml` declares Python 3.10+ and the package layout, but does not define
  separate product/study test commands.

**Tasks**

- [x] Create `tests/product/` and move increment/product regressions without
      changing their assertions.
- [x] Create `tests/study/` for downloader and optional reference-presence checks.
- [x] Replace hard-coded root-directory assertions with a checked-in provenance
      manifest/configuration lookup. Accept both a clean product checkout with no
      references and an explicitly configured study checkout.
- [x] Keep the exact expected-module inventory; update it only in the PR adding an
      approved module.
- [x] Add an offline CI job for every supported Python version using only the local
      package and `tests/product/`.
- [x] Keep study tooling outside the required product CI job and make optional
      reference-presence checks skip cleanly when material is absent.
- [x] Document build isolation. If the build backend can cause dependency fetching,
      document the pre-provisioned/offline invocation rather than claiming that
      package installation is always network-free.
- [ ] Import or locate `REANALYSIS.md` and `results/`, record hashes, and reconcile
      their 27-file manifest with the module inventory. Do not fabricate placeholders.
- [x] Separate journal conflicting-identity tests from public route-retry tests;
      both contracts remain required until PR 3 deliberately changes retry behavior.
- [x] Add owned expected-failure regressions for the PR 1 known-invoice and
      held-reservation-after-halt defects. Their owning PR must convert them to
      ordinary passing tests; expected-failure status is not acceptance.

**Acceptance**

- [x] `PYTHONPATH=src python -m unittest discover -s tests/product -t . -v` passes in a clean checkout
      containing only product sources, product tests, metadata, and documentation.
- [x] The product command requires no reference clone, credentials, network,
      checkpoint, dataset, or manually created empty directory.
- [x] Optional study checks clearly report `skipped` when evidence trees are absent.

---

## PR 1 — financial truth independent of semantic validity

**Goal:** record the bill that happened even when the response is unusable.

**Observed gaps and retained behavior**

- `OptionExecutor` replaces the entire `OperationResult` when an outcome is not a
  graph branch. That discards known cost, output reference, and provider receipt.
- `SQLiteBudgetLedger.settle` already persists an over-bound actual cost, marks the
  reservation breached, halts the budget, and then raises.
- `authorize_attempt` does not check the budget's halted flag before authorizing an
  earlier held reservation.
- `reserve_and_authorize` checks halt only while creating a new reservation; an
  existing held reservation can proceed to a new authorization.
- exception/timeout paths currently become unknown usage and retain a hold; preserve
  that behavior.

**Tasks**

- [x] Separate semantic branch normalization from financial/receipt normalization.
      Preserve `usage_state`, `actual_cost`, and `provider_receipt` when mapping an
      invalid semantic outcome to a typed error/unknown branch.
- [x] Settle every known invoice before deciding whether its semantic response is
      usable.
- [x] Add a typed trace/event distinction between invalid semantic outcome and
      unknown financial usage.
- [x] Add a halt check to new authorization creation for held reservations.
- [x] Apply the same check to combined reserve-and-authorize and separate authorize.
- [x] Perform exact authorization replay lookup before the halt rejection so an
      already issued identical record remains readable/idempotent without creating
      new authority.
- [x] Keep settlement, pending reconciliation, and exact invoice replay available
      after halt.
- [x] Document that post-breach recording cannot retroactively enforce an upstream
      provider bound.

**Acceptance regressions**

- [x] Bound 5 + invalid semantic outcome + known cost 20 records confirmed spend 20,
      retains the receipt, marks breach, and halts the budget.
- [x] A held-only reservation cannot receive a new attempt authorization after halt.
- [x] Both authorization entry points enforce the same halt semantics.
- [x] Identical authorization and invoice replays remain idempotent.
- [x] Timeout/exception with no authoritative usage remains pending, never zero.

---

## PR 2 — executable data-flow workflows

**Goal:** replace the shared opaque payload with validated, typed artifact flow.

**Observed gaps**

- every node receives the original `ExecutionRequest.payload`;
- outputs are retained only as flat attempt references;
- terminal output is selected by “latest output,” so checker diagnostics can replace
  the candidate answer;
- exception normalization always produces `UNKNOWN`, while the validated branch set
  for deterministic tools does not include `UNKNOWN`; the subsequent `next(...)`
  lookup can therefore raise `StopIteration` for a valid graph;
- option definitions have branches but no input bindings, output roles, artifact
  compatibility rules, terminal answer binding, or resource binding.

**Tasks**

- [x] Define versioned artifact roles at minimum for original request, candidate
      answer, retrieved evidence, checker evidence, and diagnostic output.
- [x] Add typed node input bindings and declared output roles to option contracts.
- [x] Introduce an execution-state/artifact-store interface with protected references;
      do not place sensitive artifact contents in traces.
- [x] Resolve every binding and validate role compatibility before authorization or
      adapter invocation.
- [x] Bind draft candidate → checker, then draft candidate + checker evidence → repair.
- [x] Add an explicit terminal answer binding and prevent checker evidence from
      becoming the answer merely because it was emitted last.
- [x] Permit deferred workflows to retain diagnostic references without labeling
      them successful or verified.
- [x] Define exception outcomes per operation kind and require the corresponding
      branch during graph validation.
- [x] Validate missing artifacts, incompatible roles, cycles, and unauthorized
      resource bindings before the next side effect.
- [x] Version the wire format and add strict round-trip tests for bindings/artifacts.

**Acceptance regressions**

- [x] Draft/check/repair asserts exact predecessor references received by each adapter.
- [x] The terminal answer is the repaired candidate, never the checker report.
- [x] Missing or incompatible artifacts fail before another authorization.
- [x] Tool timeout and tool exception terminate through typed branches without
      `StopIteration`; known/unknown usage treatment remains financially correct.

---

## PR 3 — durable request ownership, replay, and crash recovery

**Goal:** prevent duplicate physical effects and make uncertain recovery explicit.

**Observed gaps**

- `IcebergRouter.route` appends a decision, executes, and appends an execution summary
  in separate transactions.
- an identical public retry currently reaches a journal identity conflict rather
  than a recorded completion/in-progress contract.
- attempt dispatch, provider receipt, artifacts, branch choice, and terminal state
  are not persisted as a recoverable state machine.
- ledger and journal commits are independent; there is no transactional outbox.

**Tasks**

- [x] Adopt and document the recommended retry contract: identical request identity
      plus identical canonical content returns completed state or explicit
      in-progress/unknown state; conflicting content fails before spending.
- [x] Define a canonical request/option/config fingerprint that excludes secrets but
      includes every behavior-affecting version and limit.
- [x] Add an atomic execution claim with one owner under concurrent submissions.
- [x] Persist authorized-not-dispatched, dispatched-unknown, completed, reconciled,
      and terminal-failed states.
- [x] Persist before/after transitions for authorization, dispatch, receipt, artifact,
      branch, and terminal completion.
- [x] Include node, option/config hashes, attempt/reservation/authorization IDs,
      resource identity, provider receipt, usage state, and protected references.
- [x] Add a transactional ledger outbox for ledger-owned transitions; do not infer
      atomicity from two successful independent writes.
- [x] On restart, retain uncertain liability and never blindly redispatch an
      operation that might have completed.
- [x] Add provider reconciliation/idempotency hooks without claiming exactly-once
      effects where the provider offers no such contract.
- [x] Deliberately update the identical-retry test from `JournalConflict` only when
      the new public contract is implemented; retain conflicting-payload rejection.

**Acceptance regressions**

- [x] completed retry returns the cached/recorded completion with one physical call;
- [x] concurrent duplicate submissions have one execution owner;
- [x] exact decision replay causes one physical call total;
- [x] conflicting content fails before authorization;
- [x] crash after draft/before checker preserves the draft artifact and identifies
      unresolved checker liability without redispatching blindly.

---

## PR 4 — reviewed bounds, resources, and deadlines

**Goal:** make strict eligibility depend on an enforceable provider contract.

**Observed gaps**

- dispatch selects only by generic `OperationKind` plus an operation-version string;
- bounds are supplied values, not derived from a pinned tariff and enforced limits;
- the adapter calls its injected transport once but cannot see hidden retries;
- declared `timeout_ms` is not enforced by the adapter/executor;
- no local sandbox enforces tool resource limits.

**Tasks**

- [x] Add immutable resource identity (provider/model/tool/prompt/checker revision) to
      option nodes, authorization evidence, and attempt records.
- [x] Add a versioned tariff/cap calculator using exact fixed-unit arithmetic.
- [x] Derive liability from enforced input, output, retry, tool, checker, rounding,
      and non-token charge limits; attach provenance to the bound.
- [x] Require reviewed bounded-contract evidence for strict-mode eligibility; a
      `KNOWN` label alone is insufficient.
- [x] Disable provider/SDK retry and fallback or expose every underlying attempt to
      authorization and tracing.
- [x] Enforce a caller-visible deadline around dispatch and retain unresolved
      liability after timeout/cancellation.
- [x] Document when local timeout cannot stop already dispatched remote work.
- [ ] Introduce a reviewed sandbox for untrusted local tools before claiming tool
      deadline/resource enforcement.
      The current POSIX child-process boundary enforces wall/CPU termination, but
      does not isolate filesystem or network access and is therefore not accepted
      as a sandbox for adversarial tools.
- [x] Authorize paid feature generation and checking before invocation and charge
      their explicit accounts.

**Acceptance regressions**

- [x] reviewed transport fixtures cover normal, retry, timeout, cancellation,
      malformed response, delayed billing, and over-bound invoice;
- [x] a declared 1 ms operation completing near 70 ms is not reported timely;
- [x] timeout remains financially pending absent authoritative usage;
- [x] different resources of the same operation kind cannot be silently substituted.

---

## PR 5 — exact and informative control policies

**Goal:** make baseline randomization exact, terminating, and honestly named.

**Observed gaps**

- decimal probabilities are multiplied under the ambient `Decimal` context before
  integer conversion;
- up to 256 decimal places are accepted, but the rejection sampler has a 256-bit
  source. If the denominator exceeds `2**256`, its acceptance limit is zero and the
  loop cannot terminate;
- current random mixture samples first and defers when that option is ineligible;
- `TaskRulePolicy` keys on `WorkloadId`, which is a workload/budget grouping rather
  than a request task-feature contract.

**Tasks**

- [x] Convert finite decimals to integer coefficients from `Decimal.as_tuple()`
      without arithmetic subject to ambient context; reduce by the common GCD.
- [x] Prove sampler support for the reduced denominator or reject it before sampling.
- [x] Bound rejection iterations defensively even after denominator validation.
- [x] Derive logged propensities from the exact mechanism and eligibility rule.
- [x] Preserve the existing draw-then-defer policy under an explicit baseline name.
- [x] Add a separately named feasible-mixture policy that renormalizes exact weights
      over eligible options; do not change existing semantics silently.
- [x] Rename `TaskRulePolicy` to `WorkloadRulePolicy` with a reviewed compatibility
      alias, or add explicit task/context feature contracts and a genuinely
      task-feature-aware policy.
- [x] Include frozen option/model/prompt/checker versions in experiment snapshots;
      configuration changes create new option versions.

**Acceptance regressions**

- [x] high-precision equivalent distributions terminate or reject before the loop;
- [x] reduced exact weights, empirical draw thresholds, and recorded probabilities
      agree by construction;
- [x] deterministic seeds replay identical decisions;
- [x] draw-then-defer and feasible-mixture controls have distinct names and tests;
- [x] arithmetic and document task features route differently in a heterogeneous fixture.

---

## PR 6 — leakage isolation, manifests, and complete accounting

**Goal:** make experimental information access and denominators enforceable.

**Observed gaps**

- feedback channels are fields in one event/store API, not separately authorized views;
- evaluation aggregates supplied rows but has no immutable expected-request manifest;
- there is no explicit `MISSING` service row synthesized or required for absent results;
- `AccountId` labels costs but the ledger enforces no account/subbudget ceiling;
- no transactional adaptation subbudget exists inside the total workload budget.

**Tasks**

- [x] Introduce capability-separated views/APIs for operational checker evidence,
      user feedback, training labels, and blind final evaluation.
- [x] Prevent learning/probe code from importing or receiving blind-evaluation data.
- [x] Preserve Accept/Reject/Abstain/Missing and independent objective/checker states.
- [x] Add an immutable workload manifest with expected request identities, split,
      task features, and frozen version references.
- [x] Build reports by joining results to the manifest; either emit explicit missing
      rows or fail on incompleteness according to declared mode.
- [x] Add `MISSING` to service accounting while retaining served/deferred/failed/pending.
- [x] Enforce at most one final served utility per original request.
- [x] Add transactional account/subbudget ceilings nested under the shared budget,
      including an adaptation cap.
- [x] Charge probe, feature, operational checker, serving, and audit costs inside the
      common cap when they affect decisions.
- [x] Disclose blind scoring/training cost separately and prevent final labels from
      selecting probes or updating production policy.
- [x] Require real conditional traces for workflow claims; label independent
      completion matrices as single-call synthetic/offline evidence.

**Acceptance regressions**

- [x] learning view cannot read a blind-evaluation record;
- [x] a four-request manifest plus three results reports denominator four or raises
      the configured explicit incompleteness error;
- [x] duplicate final utility for one request is rejected;
- [x] adaptation-cap exhaustion stops probes while remaining serving funds are usable;
- [x] all decision-informing paid operations appear in account totals.

---

## PR 7 — reproducible baseline experiment

**Entry gate:** PRs 0–6 complete; source/artifact provenance and applicable licenses
are resolved; frozen splits and baseline characterization plans are approved.

**Tasks**

- [x] Add 2–3 declared task families and 5–8 versioned fixed compound options.
- [x] Add deterministic, cheap/strong short-output, bounded check/repair, and other
      reviewed options without giving one mechanism privileged resources.
- [x] Reproduce fixed, feasible-mixture, and real task-feature controls first.
- [x] Implement `wr-paper-reproduction`, `wr-plus-common-guard`, and
      `wr-path-plus-common-guard` as separately named artifacts.
- [x] Record equation/source mappings, interpretation choices, fixture hashes, split
      hashes, seed, environment, and cost permissions.
- [x] Give every strategy the same option portfolio, limits, checker access,
      workload visibility, and governor.
- [x] Freeze train/calibration/probe/final-evaluation splits and count every
      decision-informing operation.
- [x] Emit utility, original-workload coverage, served-task quality, actual known
      cost, unresolved holds, latency, failures, and paired confidence intervals.
- [x] Keep hidden counterfactual/final labels unavailable to online policies.
- [x] Label local synthetic mechanics as synthetic; make no model-superiority claim.

**Acceptance**

- [x] one documented offline command reproduces baseline tables from a clean checkout;
- [ ] one smaller authorized real conditional-workflow run validates trace plumbing;
- [x] no Iceberg advantage or inherited WISERouter theorem is claimed.

The remaining real-workflow gate is deliberately blocked pending reviewed provider
or fixture authorization, tariffs, provenance, secrets/network permission, and a
declared maximum expense. The completed artifact is synthetic mechanics only.

---

## PR 8 — Iceberg incremental evidence-acquisition hypothesis

**Entry gate:** PR 7 is reproducible and stable, adaptation accounting is enforced,
and the applicable acceptance gates explicitly authorize method implementation.

**Tasks**

- [ ] Add calibrated baseline outcome and cost estimators for frozen context strata.
- [ ] Implement zero-probe, cash-capped random-probe, and cash-capped stratified-probe
      variants before any learned acquisition model.
- [ ] Hold the downstream allocator fixed across probe variants.
- [ ] Add resource-aware racing as a separately named variant; avoid irreversible
      pruning from small noisy samples.
- [ ] Predeclare stopping rules inside the transactional adaptation cap.
- [ ] Report intrinsic outcome variability separately from uncertainty in estimated
      success probability.
- [ ] Compare held-out net utility/cost after adaptation expense at matched coverage
      and identical information access.
- [ ] Add learned probe value, adaptive feedback, or dynamic graphs only after the
      simpler controlled study justifies the added mechanism.

**Acceptance / stop rule**

- [ ] evidence acquisition repays its full cost relative to equal-option controls,
      or the implementation is simplified and the null result is reported;
- [ ] baselines, coverage denominators, or cost accounting are not changed after the
      result merely to manufacture an advantage.

---

## Cross-PR review checklist

- [ ] Preserve all existing passing behavioral tests unless an API change is named,
      reviewed, and accompanied by a replacement regression.
- [ ] Update module inventory and dependency rules in the same PR as a new module.
- [ ] Keep expected cost separate from admission liability and exact actual cost.
- [ ] Keep unknown usage pending and retries separately authorized.
- [ ] Keep user, checker, and objective observations separate.
- [ ] Record provenance, versions, commands, environment, permissions, cost, logs,
      and limitations for every reproduction.
- [ ] Never describe mocks/synthetic tables as provider, upstream, or paper parity.
- [ ] Defer Java/TypeScript policy ownership, distributed accounting, transformers,
      unrestricted graph search, and dynamic topology until the Python protocol and
      baseline evidence justify them.
