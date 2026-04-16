# ADR-0003: Core State Model

## Status
Accepted

## Context
The earlier system allowed behavior and state to drift apart. Replay and
verification were weak because the source of truth was not explicit enough.

## Decision
The durable system of record is built around these entities:
- Project
- Run
- Module
- Task
- Capability
- Decision
- Artifact
- Approval
- Budget
- Risk
- Observation

Step 1 starts by implementing `Run` as a typed and validated model rather than
as a loose dictionary payload.

## Consequences
- Natural language summaries are not authoritative.
- Planner and UI must derive from the ledger rather than inventing state.
- Schema discipline becomes a top-level design concern.
