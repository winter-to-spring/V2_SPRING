# Risk ID: RISK-0017
Title: Founder reply semantics are still ambiguous after planner escalation
Class: Before Next Phase
Status: Open
Owner: Core / Founder interaction
Observed In: Step 10 design review

## Description

Step 10 formalizes planner escalation, but founder replies are not yet typed.

That means the next phase still needs a clear distinction between:

- a hint that the planner should consider
- a direct override that should bypass planner choice
- a rejection that should block the current loop

## Impact

- human-in-the-loop semantics can blur under stress
- future founder CLI could create contradictory state transitions
- planner learning loops may misread founder responses

## Why This Matters

Hint-first only works if the system knows what a hint is.

Until founder reply semantics are typed, escalation remains only half-defined.

## Suggested Mitigation

- define a founder reply contract before the next planner-feedback phase
- separate hint, override, and rejection response types
- document which responses do and do not mutate run state directly

## Capability Gate
- Capability: founder hint loop / founder override surface
- Gate mode: Before Next Phase
- Blocked until: founder reply contract is explicit

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: ../../adr/0007-planner-decision-output-contract.md
- Design note: ../../implementation-notes/STEP_10_LANGGRAPH_PLANNER_ADAPTER.md

## Exit Criteria

- founder replies are typed and replayable
- hint-first vs override-available semantics are explicit in code and docs

## Last Updated
- 2026-04-17
