# Risk ID: RISK-0014
Title: ~~Stale planner proposals currently consume phase budget even when the fault is systemic timing drift~~
Class: Before Next Phase
Status: Resolved
Owner: Core / Planner governance
Observed In: Step 9 post-implementation review

## Description

Step 9 initially counted `rejected_stale` as a budget-consuming planner failure.

That is a simple deterministic rule, but it may be unfair in the cases where
the stale hash was caused by:

- a human changing approval state
- another worker mutating the run
- infrastructure latency between snapshot read and proposal submission

In those cases the planner did not necessarily make a bad choice; the system
state simply moved underneath it.

## Impact

- planner phases may exhaust due to timing churn rather than bad planner choices
- founders may experience avoidable exhaustion under asynchronous conditions
- real planner adapters may look worse than they are because budget is burned by
  freshness races

## Why This Matters

Once a real planner adapter is attached, stale proposals will become common
enough that budget fairness matters.

If the system treats all stale proposals as planner mistakes, bounded governance
can become a concurrency penalty instead of a planning safeguard.

## Suggested Mitigation

- split stale into a separate freshness counter / backoff policy
- include stale-rate diagnostics in replay and planner analytics
- keep stale fairness explicit before real planner attachment

## Capability Gate
- Capability: real planner adapter / asynchronous proposal submission
- Gate mode: Before Next Phase
- Blocked until: stale-budget policy is explicitly chosen

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: ../../adr/0006-bounded-replanning-governance.md
- Design note: ../../implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md

## Exit Criteria

- stale handling policy is explicit and justified
- planner budget cannot be exhausted accidentally by timing churn alone
- `stale` attempts use a separate stale quota rather than the main phase budget

## Last Updated
- 2026-04-17
