# ADR 0016: Lease renewal, fencing tokens, and stale-result rejection

## Status

Accepted

## Context

Step 17 introduced lease-aware execution claims, but three hardening gaps
remained:

- bounded TTL alone could still starve longer-running work or force premature
  reclaim
- claim acquisition semantics needed stronger atomic/CAS behavior than a plain
  check-then-write flow
- reclaim needed a clearer fence so late worker results could never be accepted
  after ownership changed

These gaps were tracked under:

- `RISK-0046`
- `RISK-0047`
- `RISK-0048`

## Decision

We harden the execution-claim model with three rules.

### 1. Thresholded lease renewal

Workers may ask to renew an active lease, but only when the remaining TTL falls
below a bounded threshold.

- workers send renewal intent
- the store remains the source of truth for `heartbeat_at` and `expires_at`
- worker clocks are not trusted for expiry decisions
- healthy leases do not write unnecessary heartbeat traffic

### 2. Version-gated atomic claim updates

Execution claim reacquire/update paths use the claim `version` as a fencing
token and compare-and-swap guard.

- each run still owns at most one claim row
- insert conflicts degrade to typed refusal
- existing-row reacquire/renew paths require the expected version/token to
  match before the update succeeds

### 3. Fenced stale-result rejection

Result submission must match the currently active task claim token and fencing
token.

- reclaimed or superseded workers cannot land accepted results
- stale results produce typed ledger/audit evidence
- reclaim remains pessimistic and founder-visible

## Consequences

### Positive

- longer-running bounded work no longer depends on one static TTL
- claim ownership becomes stronger than simple transaction ordering
- late results are rejected deterministically after reclaim
- expiry decisions are anchored to store/server time rather than worker clocks

### Negative

- claim bookkeeping grows more complex
- renew/reclaim paths add more ledger traffic
- future scale may still require batching or smarter heartbeat policy
- external side-effects remain a follow-on concern for networked runtimes

## Follow-up

- `RISK-0046`, `RISK-0047`, `RISK-0048` are addressed in current scope
- `RISK-0050` clock drift is absorbed by store-time truth and recorded as
  resolved
- `RISK-0049` heartbeat storm remains a follow-on Before Scale concern
- `RISK-0051` external side-effect ghost remains a follow-on concern before
  opening side-effectful/networked runtimes
