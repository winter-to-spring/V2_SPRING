# Risk ID: RISK-0009
Title: ~~Planner-facing audit payloads may become noisy or unsafe~~
Class: Later Hardening
Status: Resolved
Owner: Core / Observability
Observed In: Step 8 - Planner proposal contract review

## Description

Step 8 records stale and illegal planner proposal attempts as `SYSTEM_AUDIT`
observations. This is useful for replay and debugging, but it also means
planner-adjacent text fields and validation details are entering durable logs.

At current CLI scale this is acceptable, but later richer surfaces or planner
adapters may suffer if audit payloads become:

- too verbose to be useful
- inconsistent across failure types
- overly revealing about internal implementation details

## Impact

- replay and planner debugging may become noisy
- future UI or adapter layers may inherit inconsistent error payloads
- careless detail fields could expose more internal context than intended

## Why This Matters

Step 11 closes this risk for the founder/operator CLI surface by introducing a
compact progress summary layer, stable error-code extraction for recent audit
highlights, and explicit `--trace` / `--raw` escape hatches for debugging.

## Suggested Mitigation

- standardize structured error codes for stale vs illegal proposal failures
- keep audit payloads compact and free of unnecessary internal detail
- add explicit sanitization rules before richer UI or external planner surfaces

This risk is resolved for the current founder/operator surface because:

- `run status` now emits compact audit highlights with extracted `error_code`
- default progress views use sanitized `detail_preview` instead of dumping raw
  payloads directly into the cockpit
- `--trace` and `--raw` provide explicit escape hatches for debugging when the
  compact summary is not enough
- the JSON progress contract is typed, so downstream surfaces do not depend on
  ad-hoc audit dict shapes

## Capability Gate
- Capability: richer founder/operator surfaces or external planner adapters
- Gate mode: later_hardening
- Blocked until: compact and raw audit paths are both explicit and typed

## Issue Link
- GitHub Issue: #26

## Doc Links
- ADR: ../../adr/0005-founder-verification-surface.md
- Design note: ../../implementation-notes/STEP_11_FOUNDER_OPERATOR_PROGRESS_SURFACE.md

## Exit Criteria

- audit payloads use stable error categories
- planner-facing traces remain compact and safe to expose
- a founder/operator surface can reveal raw detail only through an explicit
  escape hatch

## Last Updated
- 2026-04-16
- 2026-04-17
