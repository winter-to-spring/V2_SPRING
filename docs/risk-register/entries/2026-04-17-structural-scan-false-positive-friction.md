# Risk ID: RISK-0044
Title: ~~Lightweight structural scan may create founder friction through false positives~~
Class: Before Next Phase
Status: Resolved
Owner: Patch intake policy / structural scan
Observed In: Step 16 structural scan planning

## Description

A stronger scan can reduce dangerous auto-apply misses, but conservative
heuristics may also flag harmless code and reroute too many low-risk patches
back to founder review.

## Impact

- bounded auto-apply loses much of its throughput benefit
- founder sees more manual review prompts than expected
- trust in the hardening layer drops because it feels noisy rather than sharp

## Why This Matters

The goal is productive control, not blanket suspicion.

A structural scan that cannot distinguish hard blocks from soft warnings turns
automation gains back into review fatigue.

## Suggested Mitigation

- split scan findings into strict blocks and soft warnings
- keep replay/audit visibility for both classes
- begin with a small set of high-confidence structural rules

## Resolution

Step 16 classified structural scan findings into two lanes:

- strict block findings, which make the patch ineligible for auto-apply
- soft warnings, which remain founder-visible without pretending every
  suspicious pattern is equally dangerous

This keeps the first hardening pass conservative while avoiding a blanket
"everything suspicious is a hard block" policy.

## Capability Gate
- Capability: low-friction trust hardening for bounded auto-apply
- Gate mode: Before Next Phase
- Blocked until: structural warnings do not default to universal hard block

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## Exit Criteria

- structural findings are classified into block vs warning
- tests cover representative safe patterns that should not be hard-blocked

## Last Updated
- 2026-04-17
