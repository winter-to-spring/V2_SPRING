# Step 21 - Postgres Migration And Transactional Concurrency

## What changed

- added Alembic baseline scaffolding:
  - `alembic.ini`
  - `alembic/env.py`
  - baseline revision under `alembic/versions`
- added Makefile helpers for migration-oriented workflows
- promoted JSON-heavy ledger columns to PostgreSQL `JSONB` while preserving
  SQLite compatibility through SQLAlchemy variants
- added Postgres-aware store capabilities:
  - dialect detection
  - pool pre-ping for PostgreSQL engines
  - row-lock helpers for execution-claim mutation paths
  - `FOR UPDATE` / `SKIP LOCKED` claim access on Postgres
- made schema bootstrap mode explicit:
  - SQLite remains self-bootstrapping through ORM metadata create
  - PostgreSQL now requires migration-controlled bootstrap and refuses
    implicit ORM table creation on the hot path
- added a richer `v2-spring doctor` surface so founder/operator flows can see
  current DB dialect, migration control status, revision, and missing tables
- Makefile migration helpers now prefer `.venv/bin/alembic` when available,
  reducing local bootstrap drift

## Execution-claim focus

The first migration target is the execution-claim hot path:

- acquire
- renew
- release
- reclaim

These paths now use a stronger claim-loading contract so Postgres can serialize
competing mutations around the same run or claim row.

## What is intentionally not done yet

- no full Postgres integration test suite against a live database in this slice
- no LangGraph Postgres persistence yet
- no Redis queue/cache/pubsub layer yet
- no final closure for connection exhaustion or contention risks

## Verification

- targeted regression tests cover Postgres-oriented store helpers and existing
  claim behavior
- full Python test suite still passes after the dialect-aware store changes
- disposable live Postgres smoke now verifies:
  - `alembic upgrade head`
  - `v2-spring doctor`
  - `v2-spring run create/show`
  against a real PostgreSQL backend

## Risk impact

- `RISK-0055` moves to mitigating through controller-first connection ownership
  guidance and Postgres pool pre-ping defaults
- `RISK-0056` moves to mitigating through Alembic baseline introduction
- `RISK-0056` is further reduced because PostgreSQL paths now fail closed when
  migrations have not been applied, instead of silently creating drift-prone
  tables from ORM metadata
- `RISK-0057` moves to mitigating through row-lock helpers, claim hot-path
  indexing, and targeted regression coverage

## Feedback Incorporated

- Migration feedback pushed this slice to treat Postgres as a transactional
  concurrency upgrade, not just a storage swap.
- That pressure directly produced Alembic-managed bootstrap, fail-closed schema
  behavior, and a clear migration path before multi-worker scale.
- Review guidance also narrowed the migration order to leases/claims first,
  then broader ledger concerns, with planner persistence explicitly later.
