# Risk ID: RISK-0011
Title: Manual recharge lacks environment preflight and misuse guardrails
Class: Before Scale
Status: Open
Owner: Core / Founder operations
Observed In: Step 9 - bounded replanning governance review

## Description

Step 9 introduces `manual_recharge` so a founder can reopen one exhausted
planner phase.

That is useful, but the current implementation only requires:

- the phase to be exhausted
- a non-blank human reason

It does not yet check whether the underlying environment, provider health, or
external dependency state has actually changed enough to justify another try.

## Impact

- founders may repeatedly recharge a phase that cannot succeed yet
- exhausted runs may churn without improving their operating context
- later scaling could turn manual recharge into accidental token waste

## Why This Matters

Manual recharge is meant to be a governance safety valve, not a blunt-force
retry button.

Without some future guardrails or preflight guidance, founders may use it in
good faith but still keep the system stuck.

## Suggested Mitigation

- add recharge preflight hints before scale
- surface the latest failure / rejection context alongside recharge guidance
- consider requiring explicit acknowledgement of unchanged environment state

## Capability Gate
- Capability: higher run volume / founder-facing UI recharge controls
- Gate mode: Before Scale
- Blocked until: recharge misuse is better guided or preflighted

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: ../../adr/0006-bounded-replanning-governance.md
- Design note: ../../implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md

## Exit Criteria

- recharge guidance or preflight exists
- founders can distinguish planner failure from environmental blockage before recharging

## Last Updated
- 2026-04-16
