# Risk ID: RISK-0055
Title: PostgreSQL connection exhaustion may appear when worker/controller fanout grows
Class: Before Next Phase
Status: Mitigating
Owner: Storage / Execution plane
Observed In: Step 21 planning

## Description

Once V2_SPRING moves from SQLite-first local execution to PostgreSQL-backed
multi-writer execution, careless connection ownership can become a new failure
mode.

If workers, containers, or multiple controller processes all try to open direct
database connections aggressively, the connection pool can saturate quickly.

## Impact

- claims, renewals, and reconciliations may block on pool exhaustion
- founder/operator CLI can appear unhealthy even when application code is fine
- background execution fanout can degrade the whole control plane

## Why This Matters

Postgres solves transactional correctness, but only if we keep access patterns
disciplined enough that the store remains available under load.

## Suggested Mitigation

- keep DB access controller-mediated by default
- configure explicit SQLAlchemy pool sizing and overflow limits
- avoid letting isolated/containerized workers talk to Postgres directly
- add operational tests that simulate fanout and observe pool pressure

Current mitigation:

- Step 21 adds PostgreSQL-specific engine defaults with pool pre-ping enabled
- controller-mediated DB access remains the default boundary; workers do not
  gain direct ledger writes in this slice
- the migration issue now treats connection ownership as a first-class design
  constraint instead of an afterthought

## Capability Gate
- Capability: multi-worker / multi-agent execution on Postgres
- Gate mode: Before Next Phase
- Blocked until: controller-mediated connection ownership and bounded pool
  behavior are implemented

## Issue Link
- GitHub Issue: #47

## Doc Links
- ADR: ../../adr/0019-postgres-migration-and-transactional-concurrency.md
- Design note: ../../issues/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md

## Exit Criteria

- worker fanout cannot exhaust the primary DB through unbounded direct
  connections
- controller pool behavior is configured and tested under expected load

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating in Step 21)
