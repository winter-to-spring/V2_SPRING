# Risk ID: RISK-0040
Title: ~~Semantic chain reaction may bypass founder review when low-risk auto-apply touches central files~~
Class: Before Next Phase
Status: Resolved
Owner: Patch intake policy / execution-plane trust gate
Observed In: Step 15 bounded auto-apply lane

## Description

A patch may look trivially small and low-risk by surface shape while still
touching a file with outsized semantic influence, such as shared constants,
core helpers, or base abstractions.

The current auto-apply policy primarily reasons from warnings, file count, and
patch breadth. That is not enough to capture file centrality.

## Impact

- low-risk auto-apply may introduce broad semantic regressions
- founder trust in automatic intake decreases
- replay remains accurate, but the damage radius of a "small" patch can still be large

## Why This Matters

The bounded auto-apply lane should only remove founder review where the blast
radius is genuinely small.

If semantically central files remain eligible, the system can silently overreach
its current trust envelope.

## Suggested Mitigation

- add protected path / protected module policy for auto-apply exclusion
- treat central files as founder-review-only even when line count and file count
  remain small
- keep the initial policy explicit and hardcoded rather than score-based

## Resolution

Step 16 introduced explicit central/protected file detection inside the bounded
auto-apply policy.

That means:

- central files are no longer auto-apply eligible just because the patch is
  small
- founder review remains mandatory for these files
- replay and founder surfaces can show the blocking reason as a typed warning

## Capability Gate
- Capability: broader trust in low-risk auto-apply beyond trivial files
- Gate mode: Before Next Phase
- Blocked until: semantic centrality is reflected in auto-apply eligibility

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## Exit Criteria

- protected or central files are explicitly excluded from auto-apply
- tests prove small patches to protected files still require founder review

## Last Updated
- 2026-04-17
