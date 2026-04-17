# Risk ID: RISK-0028
Title: Patch may apply syntactically while still introducing semantic or validation-breaking drift
Class: Before Next Phase
Status: Open
Owner: Patch intake / Validation boundary
Observed In: Step 12-c patch intake planning

## Description

A unified patch may apply cleanly against the current file state while still
being logically wrong for the surrounding system.

Examples:

- a referenced function signature changed elsewhere
- the patch compiles only partially
- runtime behavior is now inconsistent even though the textual apply succeeded

## Impact

- founder may approve a patch that silently degrades behavior
- replay may claim the patch was accepted even though the resulting code state
  was not healthy
- downstream tasks can inherit subtly corrupted code

## Why This Matters

Step 12-c is the point where execution-plane output becomes real file state.

If "apply succeeded" is treated as enough, the system can drift into silent
code corruption while still looking healthy at the ledger level.

## Suggested Mitigation

- keep patch apply strict and all-or-nothing
- run a bounded validation step immediately after apply
- record validation success/failure in the ledger and founder surface
- reject applied patches that fail validation instead of treating them as a
  successful intake

## Capability Gate
- Capability: patch intake / apply proof (Step 12-c)
- Gate mode: Before Next Phase
- Blocked until: patch intake includes explicit post-apply validation

## Issue Link
- GitHub Issue: #30

## Doc Links
- ADR:
- Design note: docs/issues/STEP_12C_PATCH_INTAKE_REVIEW_GATE.md

## Exit Criteria

- syntactic patch apply is not treated as sufficient success
- bounded validation step runs and is recorded after apply
- failed validation can reject or roll back the intake deterministically

## Last Updated
- 2026-04-17
