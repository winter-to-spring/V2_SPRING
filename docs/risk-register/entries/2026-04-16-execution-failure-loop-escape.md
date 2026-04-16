# Risk ID: RISK-0013
Title: Accepted legal proposals may loop through repeated execution failure without planner budget pressure
Class: Before Next Phase
Status: Mitigating
Owner: Core / Planner-executor boundary
Observed In: Step 9 post-implementation review

## Description

Step 9 intentionally keeps planner proposal budget separate from later executor
or runtime failure.

That is correct in one sense, because planner governance should not blame the
planner for infrastructure outages or bounded executor faults by default.

However, this also creates a new escape hatch:

- a planner can keep producing legal proposals
- those proposals can pass legality checks
- execution can keep failing for effectively the same real-world reason
- planner proposal budget may never be pressured if proposal text keeps changing

## Impact

- repeated execution failure may still create practical infinite loops
- token waste may bypass planner-side bounded governance
- replay may show many failed executions without a clear planner-level stop rule

## Why This Matters

A bounded planner loop is only truly bounded if accepted proposals cannot
indirectly keep the system spinning forever through repeated failed execution.

The planner-executor boundary needs one more rule: how execution failure feeds
back into replanning governance.

## Suggested Mitigation

- define an execution-failure feedback policy before attaching a real planner
- distinguish infra failure from repeated impossible work
- surface failed execution streaks into the next planner snapshot
- decide whether repeated execution failure should eventually escalate, block,
  or require explicit founder intervention
- Step 10 now adds a structured failure report to planner context, but stronger
  masking / escalation rules still need follow-up proof

## Capability Gate
- Capability: real planner adapter / automatic execution chaining
- Gate mode: Before Next Phase
- Blocked until: execution failure feedback is folded into bounded replanning governance

## Issue Link
- GitHub Issue: #19

## Doc Links
- ADR: ../../adr/0006-bounded-replanning-governance.md
- Design note: ../../implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md

## Exit Criteria

- repeated execution failures cannot keep causing legal planner re-entry forever
- planner snapshots carry enough execution-failure context to avoid blind retries
- a governed stop or escalation path exists for repeated failed execution cycles

## Last Updated
- 2026-04-17
