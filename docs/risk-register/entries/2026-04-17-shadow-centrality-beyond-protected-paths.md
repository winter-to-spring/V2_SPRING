# Risk ID: RISK-0045
Title: Static protected-path lists may miss semantically central files outside the initial trust boundary
Class: Later Hardening
Status: Mitigating
Owner: Patch intake policy / file centrality model
Observed In: Step 16 protected-file planning

## Description

An explicit protected-file list is a good first hardening step, but it can miss
files whose semantic importance is high even though they are not in the initial
manual list.

## Impact

- semantically central files may remain auto-apply eligible by omission
- founder may over-trust the initial protected-file boundary
- blast-radius control stays partially manual and incomplete

## Why This Matters

Static protected paths are a strong first defense, but they are not a full
centrality model.

The team should track this gap explicitly so the first implementation does not
get mistaken for the final one.

## Suggested Mitigation

- start with a conservative protected-file list
- later consider reference count, module fan-out, or test blast-radius signals
- keep this as an explicit hardening backlog item rather than hidden debt

## Current Mitigation

Step 16 introduced a first protected-file and central-file policy, so the risk
is no longer completely unguarded.

That first boundary is intentionally static and conservative, which is useful
now but still incomplete for broader autonomous trust.

## Capability Gate
- Capability: broader safe auto-apply beyond trivial or manually protected files
- Gate mode: Later Hardening
- Blocked until: dynamic or richer centrality signals supplement static path lists

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## Exit Criteria

- centrality model is expanded beyond the initial protected-file allow/deny lists

## Last Updated
- 2026-04-17
