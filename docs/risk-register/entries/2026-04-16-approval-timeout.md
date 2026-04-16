# Risk ID: RISK-0001
Title: ~~Approval timeout / deadlock can leave runs suspended forever~~
Class: Before Scale
Status: Resolved
Owner: Core orchestration
Observed In: Step 3 approval CLI review

## Description

The current approval model allows a run to remain in `waiting_approval`
indefinitely if no human resolves the gate.

## Impact

- zombie runs may accumulate
- future workers could stay blocked behind approvals that no one will answer
- human-in-the-loop becomes an unbounded pause instead of a governed pause

## Why This Matters

This is no longer left open for the current CLI substrate. The bounded
approval loop now records `expires_at`, supports explicit expiry, and moves the
run into `suspended` when a timeout sweep is applied.

## Suggested Mitigation

- add `expires_at` to approval state
- introduce `suspended` or equivalent deterministic timeout outcome
- add watchdog or sweep logic that applies the timeout policy

This risk is resolved for the current scope because:

- approvals now carry `expires_at`
- overdue approvals can be expired deterministically via `approval sweep-timeouts`
- expired approvals resolve with status `expired` and move the run to `suspended`
- replay and CLI inspection surfaces show timeout state and reason

## Capability Gate
- Capability: background worker / long-lived autonomous loop
- Gate mode: before_scale
- Blocked until: timeout semantics are implemented and documented

## Issue Link
- GitHub Issue: -

## Doc Links
- ADR: ../../adr/0002-human-in-the-loop-boundaries.md
- Design note: ../../implementation-notes/STEP_4_APPROVAL_HARDENING.md

## Exit Criteria

- approvals can expire deterministically
- expired approvals move runs into a documented terminal or suspended state
- timeout behavior is visible in CLI replay

## Last Updated
- 2026-04-17
