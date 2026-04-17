# Risk ID: RISK-0005
Title: RunSnapshot may become stale under concurrent writes
Class: Before Scale
Status: Mitigating
Owner: Core / Planner boundary
Observed In: Step 7 - RunSnapshot + possible actions; Step 12-a dispatch planning

## Description

`RunSnapshot` is built from multiple tables inside one store call. At current
CLI scale this is acceptable, but under higher concurrency a run may change
while another process is assembling or consuming a snapshot.

That means a planner or founder could read a snapshot that is already slightly
behind current reality.

In Step 12-a this risk also shows up as a dispatch/intake conflict: a worker can
start from Snapshot A, produce a patch receipt, and return after the main
workspace has moved to Snapshot B.

## Impact

- planner may act on stale context
- founder may see outdated legal moves
- worker patch intake may conflict with the code state the dispatch originally
  targeted
- later multi-worker runs could expose inconsistent reads more often

## Why This Matters

Step 7 introduces planner-ready state views. If those views become stale under
scale, later planner/replanner work will inherit an unreliable picture of the
system.

## Suggested Mitigation

- keep snapshots bounded and cheap to recompute
- include `snapshot_timestamp` and `state_hash`
- carry dispatch base context such as per-file base hashes or equivalent anchors
  into later patch intake
- reject stale or conflicting worker output through a safe conflict-aware path
- defer stronger freshness guarantees to a later concurrency hardening slice
- consider transaction boundaries, sequence numbers, or projection tables when
  multi-worker scale begins

Current mitigation:

- Step 12 added base-context-aware worker intake so stale patch receipts can be
  rejected through a safe path
- Step 17 added lease-aware execution claims so live execution ownership now
  blocks approval-sensitive mutation lanes
- expired claims can now be reclaimed and surfaced explicitly instead of
  lingering as silent ownership ambiguity

## Capability Gate
- Capability: dispatching execution work beyond simple bounded local execution
- Gate mode: Before Scale
- Blocked until: a stronger snapshot freshness strategy is chosen

## Issue Link
- GitHub Issue: #28, #41

## Doc Links
- ADR: docs/adr/0004-deterministic-substrate.md
- Design note: docs/implementation-notes/STEP_7_RUN_SNAPSHOT_POSSIBLE_ACTIONS.md
- Design note: docs/implementation-notes/STEP_12A_EXECUTION_PLANE_ROUTING_POLICY.md

## Exit Criteria

- a documented freshness contract exists for snapshot consumers
- concurrent updates cannot silently invalidate planner input without detection

## Last Updated
- 2026-04-16
- 2026-04-17
- 2026-04-17 (mitigating in Step 17)
