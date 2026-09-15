# Cost-bound specification (proposal)

## Quantities

- `budget`: exact fixed-unit shared ceiling.
- `confirmed_spend`: successfully settled charge total.
- `outstanding_liability`: sum of unreleased authorization maxima, including
  pending/unknown-usage attempts.
- `expected_cost`: selection estimate only; never used as the reservation amount
  unless independently proven to be a valid upper bound.
- `max_liability`: defensible per-authorization upper charge under versioned price,
  provider, token/tool, retry, tax/fee, and rounding assumptions.

## Admission invariant

An atomic transaction may authorize liability `L >= 0` only when checked arithmetic
establishes:

```text
confirmed_spend + outstanding_liability + L <= budget
```

All values use the same exact unit and checked range. Overflow, incomplete price
coverage, unenforceable operation limits, or an unknown bound causes denial or an
explicitly configured conservative bound—not fallback to expected cost.

## Lifecycle

1. Policy selects using expected utility/cost and logs all eligible alternatives.
2. Governor calculates and records bound inputs/version.
3. Governor atomically reserves `max_liability` and emits one authorization ID.
4. Executor creates one attempt ID per paid call; retries require new authorization.
5. Known authoritative actual cost settles idempotently and releases only the
   corresponding excess reservation.
6. Timeout, cancellation, missing usage, or ambiguous provider response becomes
   pending and retains liability until authoritative reconciliation or a documented
   safe expiry rule.
7. Duplicate identical settlement is a no-op; conflicting settlement is rejected
   and audited.

## Required bound coverage

Include every billable input/output/cache/tool/search/storage fee, minimum charge,
rounding rule, currency conversion if any, and all conditional/retry attempts.
Version prices and retain the source used at authorization time. A provider token
cap is insufficient when other charge components are unbounded or undocumented.

## Concurrency and durability

Authorization and balance update require a transactional compare-and-write or an
equivalent serializable single-writer protocol. Atomic file replacement alone does
not prevent two readers from reserving the same funds. Crash recovery must rebuild
confirmed and outstanding amounts from durable append-only events.
