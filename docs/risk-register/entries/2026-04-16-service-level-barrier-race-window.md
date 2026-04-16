# Risk ID: RISK-0004
Title: Service-level approval barrier still leaves a concurrency race window
Class: Before Scale
Status: Open
Owner: Core orchestration
Observed In: Step 4 approval boundary review

## Description

The current approval barrier is enforced in the service layer.

That is correct for the tracer bullet, but it is not yet the same thing as a
DB-level or distributed lock.

If multiple workers start mutating the same run concurrently in a later phase,
there is still a race window between read and write.

## Impact

- concurrent workers could slip conflicting writes through
- approval semantics could look correct in single-process CLI tests but fail
  under parallel execution
- replay would show contradictory ordering even though each caller behaved
  "correctly" in isolation

## Why This Matters

The current service-level barrier is enough for Phase 1 CLI validation.

It is not enough for worker pools, distributed execution, or any background
loop that writes to the same run concurrently.

## Suggested Mitigation

- introduce stronger DB-level locking or version checks for approval-gated runs
- pair that with lease-aware worker coordination
- document conflict behavior in the future HTTP/API contract

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
- approval barrier semantics stay correct with multiple writers
- concurrency behavior is tested, not assumed

## Last Updated
- 2026-04-16
