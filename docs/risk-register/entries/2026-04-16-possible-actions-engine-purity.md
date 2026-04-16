# Risk ID: RISK-0007
Title: ~~Possible-actions engine purity may drift as planner logic grows~~
Class: Before Next Phase
Status: Resolved
Owner: Core / Planner boundary
Observed In: Step 8 - Planner proposal contract review

## Description

Step 8 intentionally reuses the same `evaluate_possible_actions()` engine for:

- founder-visible legal-move inspection
- planner proposal legality checks

That is the right deterministic design, but it also creates a new dependency:
the engine must remain pure and side-effect free.

If future changes add hidden reads with side effects, cache mutation, or
environment-dependent branching, the same engine could produce subtly different
results across snapshot rendering and proposal validation.

## Impact

- planner legality checks may drift from founder-visible action menus
- repeated engine evaluation may mutate state indirectly
- debugging becomes harder because the "single source of truth" is no longer
  actually deterministic

## Why This Matters

The planner boundary is only trustworthy if the legal-move engine stays pure.
Once a real planner adapter is attached, hidden engine side effects could
create extremely confusing failures that look like planner bugs but are really
substrate bugs.

## Suggested Mitigation

- keep `evaluate_possible_actions()` free of DB writes and hidden cache writes
- document purity as a hard rule in planner-side ADRs
- add tests that prove repeated evaluation does not change run state
- treat any future data dependency expansion as a contract change, not an
  incidental refactor

## Capability Gate
- Capability: attaching a real planner adapter / replanner loop
- Gate mode: Before Next Phase
- Blocked until: the action engine purity contract is documented and verified

## Issue Link
- GitHub Issue: #15

## Doc Links
- ADR: ../../adr/0004-deterministic-substrate.md
- Design note: ../../implementation-notes/STEP_8_PLANNER_PROPOSAL_CONTRACT.md

## Exit Criteria

- repeated action evaluation is proven side-effect free
- planner legality checks and founder-visible action menus share one pure rule path
- ADR-0004 explicitly treats the possible-actions engine as a pure read-side rule engine

## Last Updated
- 2026-04-16
