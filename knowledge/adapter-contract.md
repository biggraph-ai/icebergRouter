# Common contract specification

This document defines Iceberg-owned semantic requirements, not an upstream API.
Increment 1 implements the portable scalar, decision, execution/usage-event, and
feedback records under `src/iceberg_router/contracts`; Increment 2 implements the
single-host ledger/governor; Increment 3 implements bounded option definitions and
static graph validation; Increment 4 implements guarded execution against injected
adapters; Increment 5 implements the local append-only outcome journal; and
Increment 6 implements fixed, task-rule, and random-mixture controls. Real provider
adapters and the adaptive Iceberg policy remain specifications for later increments.

## Portable scalar rules

- Identifiers, policy versions, model/provider versions, and timestamps are
  immutable strings; attempts receive distinct IDs, including retries.
- Money is a checked signed/unsigned integer fixed unit internally (proposed:
  nanodollars) and a base-10 integer string in portable JSON. Floats are forbidden
  for authorization, reservation, settlement, and invoice totals.
- Scores may be finite numeric values but carry a declared meaning and calibration
  version; they are not money or probabilities by implication.
- Enum-like states are closed/versioned. Unknown usage, missing feedback, and
  objective unknown are explicit values, never null-to-zero coercions.

## `OptionExecutor`

Input: immutable request ID, option version, bounded operation plan, authorization
ID, attempt ID, deadline, and provider-independent payload.
Output: an executed trace plus terminal attempt state, output/error reference,
reported usage or `unknown`, and settlement evidence.

Requirements: execute only authorized operations; make each conditional branch and
nested/retry attempt visible; never create authorization; never declare an unknown
charge to be zero; do not conflate provider fallback with quality escalation.

## `RoutingPolicy`

Input: versioned request features, eligible option snapshots, expected costs,
declared score semantics, and policy-visible state.
Output: decision ID, eligibility/reasons for every option, selected option or
deferral, selection probability (including deterministic 0/1), policy/snapshot
version, and native decision metadata.

Requirements: selection estimates utility and expected cost only. It does not
authorize spend. Randomness must be reproducible from logged seed/stream identity.

## `BudgetGovernor`

Operations: quote/validate a defensible upper liability; atomically reserve;
authorize a uniquely identified attempt; settle known actual cost idempotently;
mark unresolved usage pending; reject conflicting settlement; expire only under a
documented safe rule; and expose an auditable balance snapshot.

Invariant: checked confirmed spend plus all outstanding authorized liability must
not exceed the shared budget under the recorded bound assumptions. Retry, probe,
router, embedding, retrieval, verifier, sentinel, and nested operations use explicit
accounts and cannot bypass admission.

## `OutcomeStore`

Append immutable decision, authorization, trace-event, execution, usage, and
settlement records. Corrections append compensating/versioned records rather than
rewriting history. The schema distinguishes native policy choice from a common
guard rejection and distinguishes synthetic counterfactual tables from executed
paths.

Increment 5 supplies a closed event-type journal, canonical portable JSON payloads,
atomic batches, idempotency keys, explicit correction links, SQLite mutation
guards, and a verifiable hash chain. Authorization and settlement have generic
journal record types but are not yet automatically coupled to ledger transactions;
callers must reconcile journal coverage against authoritative ledger state.

## `FeedbackStore`

Record user preference as accept/reject/abstain/missing independently from
objective correctness as pass/fail/unknown, with provenance, timestamp, target
output, evaluator version, and visibility time. Verifier audits do not synthesize
unobserved alternative outcomes.

## `OptionDefinition`

Proposed shared value object: stable option/version ID, applicability predicate,
bounded conditional policy graph, per-operation accounts and enforceable limits,
expected-cost estimator/version, upper-liability calculator/version, executor
adapter, and declared feedback requirements. A policy graph is not serialized as a
flat list; an execution trace records only realized branches plus decision points.

## Compatibility rule

Adapters translate a pinned upstream decision into these records without changing
the upstream algorithm. Any added admission guard, unavailable option, changed
cost, or substituted scorer is logged as an adaptation and named separately.
