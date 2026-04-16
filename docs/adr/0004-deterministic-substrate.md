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
- V2 starts with a hybrid persistence model:
  - state tables for current truth
  - append-only event ledger for replay and audit

## Consequences
- Queue, lease, cancel, retry, and resume semantics must be explicit.
- Reconciliation and replay are mandatory.
- Planner/executor contracts must be narrow and testable.
