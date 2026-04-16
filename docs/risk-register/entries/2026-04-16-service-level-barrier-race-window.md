# Risk ID: RISK-0004
Title: ~~Service-level approval barrier still leaves a concurrency race window~~
Class: Before Scale
Status: Resolved
Owner: Core orchestration
Observed In: Step 4 approval boundary review

## Description

The original approval barrier was enforced by reading run state in the service
layer and then proceeding with writes.

That was enough for early tracer-bullet validation, but it left a race window
between "I checked the run status" and "I started writing".

## Impact

- concurrent workers could slip conflicting writes through
- approval semantics could look correct in single-process CLI tests but fail
  under parallel execution
- replay would show contradictory ordering even though each caller behaved
  "correctly" in isolation

## Why This Matters

This current-scope risk is now resolved for the single-node / current database
mode because stateful mutation paths acquire a guarded run mutation slot in the
same transaction before continuing.

## Suggested Mitigation

- introduce stronger DB-level locking or version checks for approval-gated runs
- pair that with lease-aware worker coordination
- document conflict behavior in the future HTTP/API contract

This risk is resolved for the current scope because:

- decision and observation writes now re-check run state under an atomic
  guarded mutation step instead of trusting an earlier stale read
- bounded execution start uses the same guarded status acquisition pattern
- stale callers are deterministically rejected instead of slipping through a
  purely in-memory approval barrier
- regression tests now prove the barrier re-checks current DB state before
  mutating

## Capability Gate
- Capability: background workers / concurrent run mutation
- Gate mode: before_scale
- Blocked until: approval gating is backed by stronger concurrency controls

## Issue Link
- GitHub Issue: -

## Doc Links
- ADR: ../../adr/0002-human-in-the-loop-boundaries.md
- Design note: ../../implementation-notes/STEP_4_APPROVAL_HARDENING.md

## Exit Criteria

- concurrent mutation is either prevented or deterministically rejected
- approval barrier semantics stay correct with multiple writers in the current
  single-node/store scope
- concurrency behavior is tested, not assumed

## Last Updated
- 2026-04-17
