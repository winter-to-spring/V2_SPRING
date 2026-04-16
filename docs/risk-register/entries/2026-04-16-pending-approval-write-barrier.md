# Risk ID: RISK-0003
Title: Pending approval lacks a write barrier for non-approval state changes
Class: Before Next Phase
Status: Mitigating
Owner: Core orchestration
Observed In: Step 3 approval CLI review

## Description

If a run is waiting for approval but other service entrypoints can still write
new decisions or observations, the approval gate becomes advisory instead of
authoritative.

## Impact

- state can drift while the human believes the run is paused
- future autonomous workers could mutate a run behind a pending gate
- replay becomes harder to trust because approval no longer clearly partitions
  execution

## Why This Matters

A semi-automatic system only works if approval boundaries are real. Even before
DB-level locking, the service layer must reject writes that cross a pending
approval gate.

## Suggested Mitigation

- add a service-level invariant that blocks non-approval writes while a run is
  `waiting_approval`
- keep approval resolution as the only allowed mutation during that state
- later strengthen this with DB/lease-aware concurrency controls

## Capability Gate
- Capability: planner / worker-driven mutations after intake
- Gate mode: before_next_phase
- Blocked until: service-level write barrier is enforced

## Issue Link
- GitHub Issue: #7

## Doc Links
- ADR: ../../adr/0002-human-in-the-loop-boundaries.md
- Design note: ../../implementation-notes/STEP_4_APPROVAL_HARDENING.md

## Exit Criteria

- new non-approval writes fail while approval is pending
- approval resolution remains allowed
- the CLI and tests prove the barrier exists

## Last Updated
- 2026-04-16
