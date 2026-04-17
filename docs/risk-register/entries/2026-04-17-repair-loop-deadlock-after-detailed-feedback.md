# Risk ID: RISK-0043
Title: ~~Detailed repair feedback may still trap the planner in a bounded but wasteful repair loop~~
Class: Before Next Phase
Status: Resolved
Owner: Patch repair loop / planner governance
Observed In: Step 16 repair feedback planning

## Description

Detailed validation feedback increases planner repair quality, but it can also
encourage repeated near-miss retries against the same target.

Without an explicit repair quota, the planner may keep making tiny patch
variations that consume time and model budget without materially improving the
outcome.

## Impact

- token and latency waste accumulates in the repair loop
- founder may believe the system is self-healing while it is actually stalled
- the execution plane becomes busy without making meaningful progress

## Why This Matters

Detailed repair feedback is only valuable if it converges.

If the loop can continue indefinitely, the added intelligence becomes a new
source of operational drag.

## Suggested Mitigation

- add a bounded repair quota per target or patch family
- escalate to founder review or equivalent bounded stop after repeated failure
- keep repair-loop state replay-visible

## Resolution

Step 16 turned patch validation failure into detailed repair feedback and added a
bounded repair quota over the same patch scope.

Once repeated repair failures cross the configured limit:

- the system records a founder escalation observation
- the loop becomes founder-visible instead of silently cycling
- repair feedback remains available for the last failed attempt

## Capability Gate
- Capability: autonomous patch repair after auto-apply failure
- Gate mode: Before Next Phase
- Blocked until: repair retries are bounded and failure to converge is visible

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## Exit Criteria

- repair retries are quota-bound
- exhaustion produces typed founder-visible escalation or stop semantics

## Last Updated
- 2026-04-17
