# Risk ID: RISK-0008
Title: ~~Planner proposal loop lacks retry bounds and idempotency policy~~
Class: Before Next Phase
Status: Resolved
Owner: Core / Planner boundary
Observed In: Step 8 - Planner proposal contract review

## Description

Step 8 proved that planner proposals could be accepted or rejected safely, but
it did not yet define what should happen when the same planner repeatedly
submits:

- the same stale proposal
- the same illegal action
- the same legal proposal multiple times

That gap is now closed in Step 9 with:

- phase-scoped retry budget
- explicit `phase_exhausted` outcome
- transport-level duplicate handling via `submission_key`
- cognitive duplicate handling via proposal fingerprint and accepted-proposal
  guard
- founder-controlled `manual_recharge`

## Impact

- future planner adapters may waste tokens by looping on the same bad move
- duplicate accepted proposals may clutter the decision trail
- the system may fail "correctly" but still burn time and budget indefinitely

## Why This Matters

The next phase introduces a real planner slot. Before that happens, the system
needed a bounded failure policy so planner mistakes remain observable,
governed, and finite.

## Suggested Mitigation

- keep semantic duplicate detection risk tracked separately
- keep recharge misuse / preflight concerns tracked separately
- revisit stronger planner-loop controls when a real planner adapter is attached

## Capability Gate
- Capability: real planner adapter / automatic replanning loop
- Gate mode: Before Next Phase
- Blocked until: completed in Step 9

## Issue Link
- GitHub Issue: #17

## Doc Links
- ADR: ../../adr/0006-bounded-replanning-governance.md
- Design note: ../../implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md

## Exit Criteria

- stale and illegal proposal retries have a bounded policy
- duplicate planner submissions have a documented handling rule
- planner loops cannot spin forever without surfacing a governed failure mode

## Last Updated
- 2026-04-16
