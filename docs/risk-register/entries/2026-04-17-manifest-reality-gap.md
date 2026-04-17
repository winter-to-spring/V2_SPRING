# Risk ID: RISK-0039
Title: ~~Static capability manifests may drift away from actual runtime health and create false preflight confidence~~
Class: Before Scale
Status: Resolved
Owner: Execution plane / Capability preflight
Observed In: Step 14 static-first preflight planning

## Description

Static manifests are the right starting point for Step 14, but they can become
stale or wrong.

An image may declare that a tool exists while the real binary is broken,
misconfigured, or otherwise unusable at runtime.

That creates a gap between what preflight believes and what the worker can
actually execute.

## Impact

- dispatch passes preflight but fails immediately at runtime
- planners may loop because the failure appears contradictory
- operator trust in the manifest/preflight layer erodes over time

## Why This Matters

Static-first is the right initial choice, but long-term safety needs a path from
declared capability to observed capability.

## Suggested Mitigation

- begin with static manifest checks
- record observed capability failures
- escalate selected runtime lanes to dynamic admission checks when repeated or
  high-risk mismatches are seen

Current mitigation:

- Step 19 adds central runtime trust state for execution runtimes
- repeated capability mismatches now record trust strikes instead of remaining
  invisible
- three consecutive mismatch failures promote the runtime into dynamic
  preflight
- two successful dynamic-preflight executions recover the runtime back to
  static-first mode
- founder/operator surfaces can inspect the active trust mode directly

## Capability Gate
- Capability: broader containerized worker capability expansion
- Gate mode: Before Scale
- Blocked until: runtime capability trust can react to observed mismatch, not
  just static declarations

## Issue Link
- GitHub Issue: #45

## Doc Links
- ADR: ../../adr/0012-container-runtime-provenance-and-guardrails.md
- ADR: ../../adr/0017-runtime-trust-feedback-and-heartbeat-hygiene.md
- Design note: ../../implementation-notes/STEP_19_RUNTIME_TRUST_FEEDBACK_AND_HEARTBEAT_HYGIENE.md

## Exit Criteria

- static manifests are complemented by observed-runtime trust signals
- important capability lanes can escalate to dynamic checks when needed
- repeated manifest/reality mismatches produce typed governance outcomes

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating in Step 14)
- 2026-04-17 (resolved in Step 19)
