# Risk ID: RISK-0002
Title: Rejecting approval without feedback causes blind replanning
Class: Before Next Phase
Status: Mitigating
Owner: Core orchestration
Observed In: Step 3 approval CLI review

## Description

If a human rejects an approval without structured feedback, the planner has no
durable explanation for why the proposal was refused.

## Impact

- future planner loops may repeat the same failed proposal
- replay becomes less useful because rejection looks like a binary outcome
- human guidance becomes harder to transfer across sessions

## Why This Matters

The current tracer bullet is allowed to stay small, but it cannot teach the
planner anything if rejection feedback is missing.

## Suggested Mitigation

- require `--reason` for rejection in the CLI
- store the resolution reason in approval state
- emit the reason in append-only ledger payloads

## Capability Gate
- Capability: planner / replanner loop
- Gate mode: before_next_phase
- Blocked until: rejection feedback is durable and replayable

## Issue Link
- GitHub Issue: #7

## Doc Links
- ADR: ../../adr/0002-human-in-the-loop-boundaries.md
- Design note: ../../implementation-notes/STEP_4_APPROVAL_HARDENING.md

## Exit Criteria

- rejection requires feedback
- the reason is visible in CLI state and ledger events
- future replanner steps can consume the recorded feedback

## Last Updated
- 2026-04-16
