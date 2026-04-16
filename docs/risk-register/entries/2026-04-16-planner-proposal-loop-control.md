# Risk ID: RISK-0008
Title: Planner proposal loop lacks retry bounds and idempotency policy
Class: Before Next Phase
Status: Open
Owner: Core / Planner boundary
Observed In: Step 8 - Planner proposal contract review

## Description

Step 8 proves that planner proposals can be accepted or rejected safely, but it
does not yet define what should happen when the same planner repeatedly submits:

- the same stale proposal
- the same illegal action
- the same legal proposal multiple times

There is currently no max-retry rule, no duplicate-submission policy, and no
idempotency key for planner proposals.

## Impact

- future planner adapters may waste tokens by looping on the same bad move
- duplicate accepted proposals may clutter the decision trail
- the system may fail "correctly" but still burn time and budget indefinitely

## Why This Matters

The next phase introduces a real planner slot. Before that happens, the system
needs a bounded failure policy so planner mistakes remain observable, governed,
and finite.

## Suggested Mitigation

- define a planner-side retry policy for stale/illegal proposals
- decide whether identical proposals should be deduplicated or recorded as
  distinct attempts
- introduce an idempotency key or equivalent submission identity once a real
  planner adapter is attached
- surface retry exhaustion as a governed run state or approval event

## Capability Gate
- Capability: real planner adapter / automatic replanning loop
- Gate mode: Before Next Phase
- Blocked until: retry and duplicate-submission policy are documented

## Issue Link
- GitHub Issue: -

## Doc Links
- ADR: ../../adr/0004-deterministic-substrate.md
- Design note: ../../implementation-notes/STEP_8_PLANNER_PROPOSAL_CONTRACT.md

## Exit Criteria

- stale and illegal proposal retries have a bounded policy
- duplicate planner submissions have a documented handling rule
- planner loops cannot spin forever without surfacing a governed failure mode

## Last Updated
- 2026-04-16
