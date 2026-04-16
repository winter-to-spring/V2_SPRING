# Risk ID: RISK-0012
Title: Cognitive duplicate detection remains exact-fingerprint only
Class: Before Scale
Status: Open
Owner: Core / Planner governance
Observed In: Step 9 - bounded replanning governance review

## Description

Step 9 distinguishes:

- transport duplicates via `submission_key`
- cognitive duplicates via exact proposal fingerprint and accepted-proposal
  guard

That is a good deterministic baseline, but it does not yet detect
semantically-equivalent retries where the planner changes wording while keeping
the same underlying move.

## Impact

- planner loops may still waste budget on near-identical retries
- analytics may underestimate repeated reasoning failure
- future cost controls may need additional heuristics

## Why This Matters

The current implementation is correct and bounded, but not yet especially
efficient against a stubborn planner that paraphrases itself.

## Suggested Mitigation

- keep exact-fingerprint detection as the deterministic base rule
- consider later semantic grouping or similarity heuristics only after the
  deterministic baseline proves stable
- expose duplicate categories clearly in replay and planner analytics

## Capability Gate
- Capability: high-volume planner loops / cost-sensitive scaling
- Gate mode: Before Scale
- Blocked until: deterministic baseline is proven and a stronger duplicate policy is chosen if needed

## Issue Link
- GitHub Issue: none yet

## Doc Links
- ADR: ../../adr/0006-bounded-replanning-governance.md
- Design note: ../../implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md

## Exit Criteria

- duplicate detection policy is explicit about exact-match limits
- scale planning chooses whether semantic duplicate detection is necessary

## Last Updated
- 2026-04-16
