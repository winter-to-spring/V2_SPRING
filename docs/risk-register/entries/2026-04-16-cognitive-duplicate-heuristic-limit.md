# Risk ID: RISK-0012
Title: ~~Cognitive duplicate detection remains exact-fingerprint only~~
Class: Before Scale
Status: Resolved
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

Examples:

- "Inspect the database schema before continuing"
- "Review the DB schema first"

## Impact

- planner loops may still waste budget on near-identical retries
- analytics may underestimate repeated reasoning failure
- future cost controls may need additional heuristics
- a real LLM may evade exact duplicate detection by paraphrasing the same move

## Why This Matters

The current implementation is correct and bounded, but not yet especially
efficient against a stubborn planner that paraphrases itself.

## Suggested Mitigation

- keep exact-fingerprint detection as the deterministic base rule
- consider later semantic grouping or similarity heuristics only after the
  deterministic baseline proves stable
- expose duplicate categories clearly in replay and planner analytics

Current resolution:

- exact proposal fingerprints remain the strict base rule
- planner governance now also computes a deterministic normalized intent
  signature from the selected action plus normalized rationale/outcome tokens
- paraphrased retries for the same action can now be rejected as
  `rejected_duplicate_cognitive` even when wording changes
- replay and planner attempt events still expose duplicate outcomes explicitly

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
- paraphrased near-duplicate retries are bounded by a deterministic heuristic

## Last Updated
- 2026-04-16
- 2026-04-17
