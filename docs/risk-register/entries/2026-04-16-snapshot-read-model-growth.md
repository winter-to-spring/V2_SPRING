# Risk ID: RISK-0006
Title: Snapshot and action read models may become expensive as run history grows
Class: Later Hardening
Status: Deferred
Owner: Core / Observability
Observed In: Step 7 - RunSnapshot + possible actions

## Description

Step 7 uses fixed-query read models and compact summaries. This is the right
tradeoff at current scale, but query cost and serialization size will grow as
run history, task counts, and artifact volume increase.

## Impact

- `run snapshot` and `run actions` may become slow
- founder/operator CLI responsiveness may degrade
- future UI adapters may need projection-specific models anyway

## Why This Matters

The current implementation is intentionally simple and bounded, but it should
not be mistaken for a final scaling strategy.

## Suggested Mitigation

- keep snapshot output summary-first
- avoid full history reads in snapshot building
- revisit materialized views or dedicated projections when scale rises

## Capability Gate
- Capability: scaling run/task counts or exposing richer founder/operator surfaces
- Gate mode: Later Hardening
- Blocked until: not blocked now; revisit before scale-oriented milestones

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: docs/adr/0005-founder-verification-surface.md
- Design note: docs/implementation-notes/STEP_7_RUN_SNAPSHOT_POSSIBLE_ACTIONS.md

## Exit Criteria

- snapshot/action query latency remains acceptable at target scale, or
- a projection/materialized-view strategy is adopted

## Last Updated
- 2026-04-16
