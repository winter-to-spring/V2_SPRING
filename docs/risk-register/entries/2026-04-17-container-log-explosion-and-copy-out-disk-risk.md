# Risk ID: RISK-0034
Title: ~~Containerized worker log explosion may exhaust host disk during copy-out or receipt collection~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Container runtime
Observed In: Step 13 containerized worker proof

## Description

Step 13 intentionally avoided Docker daemon log streaming, but that still left
a second-order risk: a runaway worker could write extremely large logs and push
copy-out risk onto the host.

## Impact

- host disk can fill during copy-out
- control-plane operations may fail or stall because the host is out of space
- receipt collection can become slower or fail in a way that obscures the real
  worker failure

## Why This Matters

The current Step 13 proof is safe against stdout/stderr pipe deadlock, but disk
pressure is a different failure mode.

If we expand worker capabilities without a log-size policy, a single runaway
worker can still degrade or crash the host.

## Suggested Mitigation

- enforce bounded file-size policy inside the containerized runtime
- add pre-copy size checks before copying worker log files back to the host
- generate a typed overflow receipt when logs exceed the safe bound
- prefer tail-first capture so bounded diagnostics still preserve the most useful
  end-of-log failure evidence
- consider shell/runtime file-size limits or equivalent guardrails for proof
  lanes that can emit large logs

Current resolution:

- containerized execution now runs through a bounded log-capture wrapper
- the wrapper persists only bounded preview artifacts plus byte-count metadata
- host-side receipt collection now copies only those bounded output artifacts
- diagnostics use sandwich capture (`head + tail`) rather than blind tail-only
  truncation

## Capability Gate
- Capability: broader containerized worker capability expansion
- Gate mode: Before Next Phase
- Blocked until: container log files are size-bounded or overflow-safe before
  host copy-out

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR: ../../adr/0012-container-runtime-provenance-and-guardrails.md
- Design note: ../../implementation-notes/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## Exit Criteria

- worker log growth is bounded before host copy-out
- oversized logs return a typed overflow receipt or tail-first bounded evidence
  instead of risking host disk exhaustion
- receipt collection no longer depends on full copy-out of arbitrarily large log
  files

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 14)
