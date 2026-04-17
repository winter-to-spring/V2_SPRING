# Risk ID: RISK-0042
Title: ~~Obfuscated dangerous patterns may bypass simple keyword scans in bounded auto-apply~~
Class: Before Next Phase
Status: Resolved
Owner: Patch intake policy / safety scan
Observed In: Step 15 bounded auto-apply lane

## Description

The current dangerous-pattern detection is primarily keyword-based. That catches
obvious cases but not lightly obfuscated forms such as indirect attribute
access, string concatenation, or thin wrappers around dangerous calls.

## Impact

- dangerous code may pass the auto-apply gate
- founder review may be skipped where a stronger scan would have escalated
- trust in the bounded auto-apply lane erodes quickly after a single miss

## Why This Matters

Keyword heuristics are acceptable for an initial narrow proof, but once
auto-apply is real they become a known bypass surface.

## Suggested Mitigation

- add lightweight structural or AST-based analysis for risky calls
- preserve the current keyword scan as the first cheap guard
- surface suspicious patterns to founder status and replay even when blocked

## Resolution

Step 16 supplemented the simple keyword scan with a lightweight structural scan.

The scan now:

- parses added Python source when possible
- detects high-confidence dangerous calls such as `eval`, `exec`,
  `subprocess.run`, `shutil.rmtree`, and obfuscated `getattr` variants
- distinguishes between hard structural danger and softer suspicious patterns

## Capability Gate
- Capability: trustworthy bounded auto-apply for code patches beyond trivial text edits
- Gate mode: Before Next Phase
- Blocked until: dangerous patterns cannot trivially bypass the current keyword scan

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## Exit Criteria

- lightweight structural scan supplements keyword heuristics
- tests prove representative obfuscated patterns are refused or founder-reviewed

## Last Updated
- 2026-04-17
