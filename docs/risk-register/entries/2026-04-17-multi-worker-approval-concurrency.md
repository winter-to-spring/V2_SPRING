# Risk ID: RISK-0022
Title: Multi-worker approval gating still needs lease-aware concurrency controls
Class: Before Scale
Status: Open
Owner: Core orchestration / runtime coordination
Observed In: Post-RISK-0004 concurrency split

## Description

The current approval barrier now uses a guarded mutation step that closes the
single-node race window for the tracer bullet.

That does not yet provide the full guarantees required for:

- long-lived worker pools
- multiple processes mutating the same run across hosts
- lease-aware coordination between planner, executor, and background sweepers

## Impact

- two workers may still contend on the same run in ways that require stronger
  lease or version semantics than the current local transaction guard
- provider callbacks, background loops, or HTTP workers could need explicit
  conflict contracts instead of relying on local CLI/store serialization
- scale behavior could drift from current deterministic expectations if
  coordination remains implicit

## Why This Matters

The current store-level guarded mutation is the right closure for the present
CLI and single-node substrate.

Once the system grows into real worker pools, the remaining concurrency problem
is no longer "approval barrier missing" but "cross-worker coordination not yet
formalized".

## Suggested Mitigation

- introduce lease-aware worker coordination for run mutation lanes
- pair guarded writes with stronger version checks or DB-native locking
- define conflict and retry behavior for HTTP/API and background workers
- test multi-process contention explicitly instead of extrapolating from local
  CLI behavior

## Capability Gate
- Capability: multi-worker execution / background loops / distributed mutation
- Gate mode: before_scale
- Blocked until: cross-worker mutation coordination is implemented and tested

## Issue Link
- GitHub Issue: -

## Doc Links
- ADR: ../../adr/0002-human-in-the-loop-boundaries.md
- Design note: ../../implementation-notes/STEP_4_APPROVAL_HARDENING.md

## Exit Criteria

- cross-worker mutation conflicts are either serialized or deterministically
  rejected
- approval semantics remain correct with multiple concurrent processes
- lease/version behavior is visible in tests and replay/audit surfaces

## Last Updated
- 2026-04-17
