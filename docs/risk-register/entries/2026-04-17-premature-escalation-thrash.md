# Risk ID: RISK-0016
Title: Planner may escalate too early or too often once escalation becomes a legal output type
Class: Before Next Phase
Status: Open
Owner: Core / Planner governance
Observed In: Step 10 design review

## Description

Step 10 correctly introduces `EscalationProposal` as a separate planner output
type.

That solves the "enum trap", but it also creates a new risk:

- the planner may escalate at the first sign of complexity
- the planner may repeat the same escalation in slightly different words
- the system may end up safe but operationally stalled

## Impact

- founder/operator fatigue
- planner autonomy collapsing into human babysitting
- replay noise from repeated escalations

## Why This Matters

Escalation must remain a meaningful governance path, not an easy escape hatch.

Without stronger policy, the planner can trade one bad behavior (hallucinated
actions) for another (constant escalation).

## Suggested Mitigation

- add escalation policy guidance to the planner prompt
- use **phase-scoped escalation quotas** instead of time-based cooldowns
- record duplicate escalation fingerprints explicitly
- define stronger founder reply semantics before opening richer planner loops
- if a planner burns the founder-hint quota for the current phase, transition the
  current loop into a bounded exhausted state instead of allowing endless ping-pong

## Capability Gate
- Capability: planner-backed tracer bullet / founder hint loop
- Gate mode: Before Next Phase
- Blocked until: escalation behavior is bounded enough to avoid thrash

## Issue Link
- GitHub Issue: #22

## Doc Links
- ADR: ../../adr/0007-planner-decision-output-contract.md
- Design note: ../../implementation-notes/STEP_10_LANGGRAPH_PLANNER_ADAPTER.md

## Exit Criteria

- repeated escalations cannot silently stall the system
- planner prompt and governance make escalation a last-resort path rather than a default move
- founder hint / escalation ping-pong is bounded per phase

## Last Updated
- 2026-04-17
