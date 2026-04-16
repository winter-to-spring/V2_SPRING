# ADR-0005: Founder Verification Surface

## Status
Accepted

## Context
V1 allowed the system to "run" without allowing a founder to independently
verify what happened.

## Decision
Founder verification is a core architecture requirement. The system must expose
input, process, decisions, artifacts, approvals, and outcomes in a replayable
form. The first proof of this is CLI-based, not UI-based.

Founder/operator progress surfaces follow these additional rules:

- the progress surface is an **on-the-fly projection**, not a separately written
  summary table
- compact founder-facing summaries are the default surface
- explicit `raw` / `trace` escape hatches exist for debugging without polluting
  the default cockpit
- founder-facing JSON output must be backed by typed read models so later UI or
  automation can reuse the same contract safely
- founder interaction ergonomics should prefer short enum + text commands, with
  file-based escape hatches for multiline input

## Consequences
- Replayable event history is mandatory.
- Artifact and decision storage are not optional.
- Founder-facing UI comes after CLI-verifiable evidence exists.
- Founder/operator progress views must stay consistent with replay because they
  are derived from the same underlying ledger-backed state.
