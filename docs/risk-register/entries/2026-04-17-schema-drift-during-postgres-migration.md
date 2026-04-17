# Risk ID: RISK-0056
Title: Schema drift may break Postgres migration without versioned migration control
Class: Before Next Phase
Status: Mitigating
Owner: Storage / Core schema
Observed In: Step 21 planning

## Description

Moving the ledger and execution-control substrate onto Postgres raises the cost
of schema drift.

If table shape changes are applied ad hoc or only through implicit ORM
bootstrap, different environments can run incompatible schemas without obvious
warning.

## Impact

- deploys may fail because code and DB schema disagree
- replay/audit semantics may silently diverge across environments
- new transactional paths can become unreliable or impossible to migrate safely

## Why This Matters

V2_SPRING depends on ledger continuity and deterministic replay. Schema history
must be versioned as carefully as code history.

## Suggested Mitigation

- adopt Alembic or equivalent versioned schema migration tooling
- make migration state part of the official bootstrap flow
- ensure local/dev/prod all advance schema through the same migration chain

Current mitigation:

- Step 21 introduces an Alembic baseline, env, and revision history scaffold
- Makefile migration targets now give the repo an explicit migration workflow
- the PostgreSQL migration issue now treats schema evolution as versioned repo
  state rather than implicit ORM side effects
- PostgreSQL hot paths now fail closed when migrations are missing, instead of
  silently bootstrapping drift-prone tables from ORM metadata
- `v2-spring doctor` can report migration control status and missing tables so
  bootstrap drift is visible before normal control-plane commands run

## Capability Gate
- Capability: Postgres-first primary store
- Gate mode: Before Next Phase
- Blocked until: schema evolution is tracked through versioned migrations

## Issue Link
- GitHub Issue: #47

## Doc Links
- ADR: ../../adr/0019-postgres-migration-and-transactional-concurrency.md
- Design note: ../../issues/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md

## Exit Criteria

- schema changes are versioned and replayable through a migration tool
- new environments can bootstrap to the exact expected schema deterministically

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating in Step 21)
- 2026-04-17 (migration-controlled bootstrap enforced in code)
