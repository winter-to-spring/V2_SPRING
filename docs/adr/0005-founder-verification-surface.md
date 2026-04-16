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

## Consequences
- Replayable event history is mandatory.
- Artifact and decision storage are not optional.
- Founder-facing UI comes after CLI-verifiable evidence exists.
