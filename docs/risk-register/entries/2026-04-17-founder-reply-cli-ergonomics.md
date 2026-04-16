# Risk ID: RISK-0018
Title: ~~Founder reply CLI ergonomics may cause operator error before a richer surface exists~~
Class: Later Hardening
Status: Resolved
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

Step 11 closes this risk for the current CLI surface by narrowing the founder
reply commands and adding file-based input escape hatches for multiline hints
and reasons.

## Suggested Mitigation

- prefer short enum + text contracts over free-form JSON input
- keep `hint`, `override`, and `reject` entrypoints explicit and narrow
- add richer founder/operator surfaces later without changing the underlying
  typed contract

This risk is resolved for the current founder/operator CLI because:

- founder reply entrypoints stay explicit (`hint`, `override`, `reject`)
- multiline input now has file-based escape hatches (`--message-file`,
  `--reason-file`) instead of forcing shell-escaped inline text only
- the Step 11 progress surface now shows the relevant founder command examples
  next to the blocking status
- the typed founder reply contract is unchanged, so richer surfaces can reuse it

## Capability Gate
- Capability: broader founder-facing planner interaction surface
- Gate mode: later_hardening
- Blocked until: concise command paths and multiline input escape hatches exist

## Issue Link
- GitHub Issue: #26

## Doc Links
- ADR: ../../adr/0007-planner-decision-output-contract.md
- Design note: ../../implementation-notes/STEP_11_FOUNDER_OPERATOR_PROGRESS_SURFACE.md

## Exit Criteria

- founder reply CLI commands are concise and hard to misuse
- multiline founder hints and reasons do not require brittle shell escaping
- a richer founder surface can reuse the same typed reply contract

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 11)
