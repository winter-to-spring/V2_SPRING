# Risk ID: RISK-0041
Title: ~~Planner may game bounded auto-apply by slicing one risky change into many trivial patches~~
Class: Before Next Phase
Status: Resolved
Owner: Patch intake policy / planner governance
Observed In: Step 15 bounded auto-apply lane

## Description

A planner can preserve apparent low-risk shape by splitting one larger change
into many small, single-file patches that each look safe enough for auto-apply.

The current lane does not yet throttle repeated auto-apply events against the
same file or module over a short horizon.

## Impact

- significant code drift can occur without a single founder review
- audit remains accurate but operational trust declines
- planner may optimize for the policy rather than the real task boundary

## Why This Matters

Bounded auto-apply should accelerate obvious safe edits, not become a loophole
for piecemeal delivery of a large risky change.

## Suggested Mitigation

- add burst quotas for repeated auto-apply events
- fallback to founder review when the same file or module is touched repeatedly
- make the throttle typed and replay-visible rather than silent

## Resolution

Step 16 added a bounded auto-apply burst guard over a replay-visible policy
window.

The current guard:

- counts recent `AUTO_APPLIED` patch intake events
- detects overlap by file or module scope
- forces founder review when repeated low-risk slices begin to look like one
  larger rolling change

## Capability Gate
- Capability: safe reuse of bounded auto-apply across repeated worker loops
- Gate mode: Before Next Phase
- Blocked until: repeated low-risk slices cannot bypass founder review indefinitely

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## Exit Criteria

- repeated auto-apply bursts are throttled or rerouted to founder review
- tests prove the planner cannot repeatedly auto-apply against the same target without limit

## Last Updated
- 2026-04-17
