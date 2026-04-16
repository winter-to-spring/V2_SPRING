# Risk ID: RISK-0018
Title: Founder reply CLI ergonomics may cause operator error before a richer surface exists
Class: Later Hardening
Status: Deferred
Owner: Core / Founder interaction
Observed In: Step 10-b founder reply contract review

## Description

Step 10-b intentionally introduces typed founder replies so escalation, hint,
override, and reject semantics become replayable and deterministic.

That is the right architectural move, but it also means the founder may need to
enter more structured data in a CLI environment before a richer UI exists.

If the CLI becomes too verbose or too JSON-heavy, the founder may:

- mistype reply kinds or action names
- provide malformed structured hints
- accidentally choose override when a hint was intended

## Impact

- human-in-the-loop control becomes harder to use under stress
- operator error may create avoidable replay noise
- a safe system may still feel hostile or brittle to the founder

## Why This Matters

The whole point of Step 10-b is to preserve founder control without turning the
system back into manual puppet-work.

If the CLI is too awkward, correctness survives but usability collapses.

## Suggested Mitigation

- prefer short enum + text contracts over free-form JSON input
- keep `hint`, `override`, and `reject` entrypoints explicit and narrow
- add richer founder/operator surfaces later without changing the underlying
  typed contract

## Capability Gate
- Capability: broader founder-facing planner interaction surface
- Gate mode: Later Hardening
- Blocked until: not blocked now; revisit before wider founder/operator rollout

## Issue Link
- GitHub Issue: #22

## Doc Links
- ADR: ../../adr/0007-planner-decision-output-contract.md
- Design note: ../../issues/STEP_10B_FOUNDER_REPLY_CONTRACT_AND_ESCALATION_LOOP.md

## Exit Criteria

- founder reply CLI commands are concise and hard to misuse
- a richer founder surface can reuse the same typed reply contract

## Last Updated
- 2026-04-17
