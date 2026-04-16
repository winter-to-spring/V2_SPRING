# Risk ID: RISK-0005
Title: RunSnapshot may become stale under concurrent writes
Class: Before Scale
Status: Deferred
Owner: Core / Planner boundary
Observed In: Step 7 - RunSnapshot + possible actions

## Description

`RunSnapshot` is built from multiple tables inside one store call. At current
CLI scale this is acceptable, but under higher concurrency a run may change
while another process is assembling or consuming a snapshot.

That means a planner or founder could read a snapshot that is already slightly
behind current reality.

## Impact

- planner may act on stale context
- founder may see outdated legal moves
- later multi-worker runs could expose inconsistent reads more often

## Why This Matters

Step 7 introduces planner-ready state views. If those views become stale under
scale, later planner/replanner work will inherit an unreliable picture of the
system.

## Suggested Mitigation

- keep snapshots bounded and cheap to recompute
- include `snapshot_timestamp` and `state_hash`
- defer stronger freshness guarantees to a later concurrency hardening slice
- consider transaction boundaries, sequence numbers, or projection tables when
  multi-worker scale begins

## Capability Gate
- Capability: opening planner/replanner beyond single-process CLI scale
- Gate mode: Before Scale
- Blocked until: a stronger snapshot freshness strategy is chosen

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: docs/adr/0004-deterministic-substrate.md
- Design note: docs/implementation-notes/STEP_7_RUN_SNAPSHOT_POSSIBLE_ACTIONS.md

## Exit Criteria

- a documented freshness contract exists for snapshot consumers
- concurrent updates cannot silently invalidate planner input without detection

## Last Updated
- 2026-04-16
