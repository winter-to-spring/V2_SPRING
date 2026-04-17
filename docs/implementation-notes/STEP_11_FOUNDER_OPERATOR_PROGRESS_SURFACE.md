# Step 11 - Founder/operator progress surface

## What changed

Step 11 adds a founder/operator cockpit on top of the existing CLI substrate.

The new surface introduces:

- `run status` as a compact progress-oriented read model
- `ProgressSummaryView` as the typed JSON contract for downstream UI/automation
- `--trace` and `--raw` escape hatches so compact summaries do not hide the
  original audit trail when debugging is required
- `--message-file` / `--reason-file` founder reply ergonomics so multiline hints
  and reasons do not require shell-escaping gymnastics

## Key design choices

### 1. On-the-fly projection, not a materialized status table

The progress surface is computed from current ledger-backed read models:

- `RunSnapshotView`
- `RunReplayView`
- current planner/founder/approval state

No separate progress/status table is written. This keeps replay and current
status aligned.

### 2. Compact by default, explicit raw escape hatch

The default progress surface is meant to answer:

- what is happening now?
- who is blocking next movement?
- what should the founder/operator do next?

When the compact summary is not enough, `--trace` and `--raw` expose additional
audit detail intentionally rather than by default.

### 3. Stable, typed JSON output

`ProgressSummaryView` is the schema-enforced JSON contract for the Step 11
surface. This prevents ad-hoc dict drift and gives later UI/dashboard work a
stable contract to reuse.

### 4. Call-to-action first

The top-level progress surface emphasizes blocker ownership:

- `waiting_on_founder`
- `waiting_on_approval`
- `suspended_on_timeout`
- `ready_for_next_action`

This keeps the cockpit focused on the next human or system action rather than
just mirroring raw run status.

## Risk register impact

- `RISK-0009` is addressed by compact audit summaries plus explicit raw/trace
  escape hatches
- `RISK-0018` is addressed by narrower founder reply commands and file-based
  input support for multiline hints/reasons

## Feedback Incorporated

- Strong feedback on "lying dashboards" pushed this slice to keep the progress
  surface as an on-the-fly projection from ledger/state, not a second mutable
  store.
- Audit hygiene feedback also required compact summaries to preserve
  raw/trace escape hatches instead of over-sanitizing founder context.
- Founder CLI ergonomics feedback directly led to file-based multiline input
  support for hints and reasons.
