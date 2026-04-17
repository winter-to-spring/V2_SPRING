# ADR 0018: Snapshot Freshness And Cancellation Reconciliation

## Status

Accepted

## Context

Step 19 left two operational integrity gaps open in the current local CLI
substrate:

- founder/operator mutation flows could still act on a snapshot that had become
  stale after inspection
- local planner cancellation was typed, but the audit trail stopped at the
  interrupt event instead of recording a bounded reconciliation outcome

V2_SPRING needs founder and operator actions to fail loudly when they are based
on outdated state, and it needs local cancellation to end in a deterministic
ledger-visible state instead of a silent "probably cancelled" assumption.

## Decision

We harden Step 20 with the following rules:

1. `RunSnapshotView` carries a `freshness_generation` in addition to the
   existing `state_hash`.
2. Founder/operator mutation lanes that depend on inspected state must accept
   explicit freshness anchors.
3. `task dispatch`, `patch approve`, and `patch reject` reject stale anchors
   through a typed `SnapshotFreshnessRefusalView`.
4. Progress and patch-review surfaces must show freshness anchors so founders
   can replay the exact mutation command safely.
5. Local planner cancellation is recorded as two audit events:
   - cancellation intent
   - local reconciliation / bounded orphan-risk finalization

## Consequences

### Positive

- stale founder/operator actions no longer mutate quietly after state drift
- progress/review surfaces expose the exact freshness contract they expect
- local cancellation leaves a clearer replay trail for later diagnosis
- Step 20 closes the current-scope snapshot freshness gap without waiting for a
  database migration

### Negative

- mutation commands now carry a small amount of extra anchor metadata
- stale founder actions fail more explicitly, which can feel stricter at first
- cancellation semantics are clearer, but provider-side orphan spend remains a
  before-scale concern

## Follow-on

- keep `RISK-0021` open until planner cancellation has stronger provider-side
  reconciliation beyond the foreground CLI
- revisit stronger transactional freshness guarantees when the Postgres
  migration starts
