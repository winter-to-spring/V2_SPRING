# Risk ID: RISK-0031
Title: ~~Containerized worker artifacts may be unreadable or undeletable on the host due to UID/GID mismatch~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Intake boundary
Observed In: Step 13 containerized worker planning

## Description

Containerized worker outputs may be written by a different UID/GID than the host
control-plane process.

If copied-out logs, receipts, or patched workspace files are left with
incompatible ownership, the host may fail to read, normalize, or clean them up.

## Impact

- patch intake can fail with permission errors
- replay artifacts can become unreadable
- cleanup may leak temp files or copied-out worker state

## Why This Matters

Step 12-c already relies on deterministic receipt and patch intake. Step 13
must preserve that loop under a container runtime, not break it at the file
handoff boundary.

## Suggested Mitigation

- launch worker containers with host UID/GID where possible
- normalize ownership after copy-out before intake reads artifacts
- keep ownership normalization explicit and testable

Implemented resolution:

- Step 13 copy-out flow normalizes containerized worker outputs on the host
- receipt metadata records whether normalization succeeded
- Step 13 tests cover successful patch/receipt intake after copy-out

## Capability Gate
- Capability: containerized patch / receipt intake
- Gate mode: Before Next Phase
- Blocked until: copied-out worker results are ownership-normalized for the host

## Issue Link
- GitHub Issue: #35

## Doc Links
- ADR: ../../adr/0011-containerized-worker-runtime.md
- Design note: ../../implementation-notes/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md

## Exit Criteria

- copied-out worker outputs are readable by the host
- cleanup path can remove worker outputs deterministically
- permission normalization is part of the runtime proof

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 13 ownership normalization)
