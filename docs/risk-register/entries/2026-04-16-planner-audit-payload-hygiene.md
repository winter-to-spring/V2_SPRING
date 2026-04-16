# Risk ID: RISK-0009
Title: Planner-facing audit payloads may become noisy or unsafe
Class: Later Hardening
Status: Deferred
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

Good failure traces should teach the system something without turning the audit
trail into a junk drawer or leaking unnecessary implementation detail.

## Suggested Mitigation

- standardize structured error codes for stale vs illegal proposal failures
- keep audit payloads compact and free of unnecessary internal detail
- add explicit sanitization rules before richer UI or external planner surfaces

## Capability Gate
- Capability: richer founder/operator surfaces or external planner adapters
- Gate mode: Later Hardening
- Blocked until: not blocked now; revisit before broader external exposure

## Issue Link
- GitHub Issue: -

## Doc Links
- ADR: ../../adr/0005-founder-verification-surface.md
- Design note: ../../implementation-notes/STEP_8_PLANNER_PROPOSAL_CONTRACT.md

## Exit Criteria

- audit payloads use stable error categories
- planner-facing traces remain compact and safe to expose

## Last Updated
- 2026-04-16
