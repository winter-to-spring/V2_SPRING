# Risk ID: RISK-0010
Title: Phase budget reset abuse may refresh planner retries without meaningful progress
Class: Before Next Phase
Status: Open
Owner: Core / Planner governance
Observed In: Step 9 - bounded replanning governance review

## Description

Step 9 resets planner retry budget per phase rather than globally per run.

That is the right default, but it creates a new risk: if future state
advancement rules become too loose, the planner could refresh its own retry
budget through low-value or purely formal progress instead of meaningful
forward movement.

## Impact

- planner retries may become effectively unbounded
- token waste could bypass phase-scoped controls
- founders may believe the loop is governed while it quietly keeps refreshing

## Why This Matters

The integrity of phase budgeting depends on a clear answer to one question:

what counts as real advancement?

If planner-only traces or low-value transitions reset budget, the governance
layer becomes cosmetic instead of protective.

## Suggested Mitigation

- keep `planner_phase_key` tied only to meaningful state advancement signals
- explicitly exclude planner-only decision summaries from phase advancement
- define future advancement rules per task/module class before opening larger
  replanning loops
- add regression tests when new advancement signals are introduced

## Capability Gate
- Capability: multi-step replanning loop / richer task graph
- Gate mode: Before Next Phase
- Blocked until: meaningful state advancement is defined per new execution mode

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: ../../adr/0006-bounded-replanning-governance.md
- Design note: ../../implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md

## Exit Criteria

- phase advancement rules are documented for each new planner-visible state
- budget cannot reset because of planner-only bookkeeping

## Last Updated
- 2026-04-16
