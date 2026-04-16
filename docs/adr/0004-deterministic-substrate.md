# ADR-0004: Deterministic Substrate

## Status
Accepted

## Context
Autonomous planning cannot be trusted if state mutation is non-deterministic or
unreplayable.

## Decision
- Postgres is the durable record store.
- Redis is coordination only.
- Planners do not mutate state directly.
- Deterministic executors perform state transitions.

## Consequences
- Queue, lease, cancel, retry, and resume semantics must be explicit.
- Reconciliation and replay are mandatory.
- Planner/executor contracts must be narrow and testable.
