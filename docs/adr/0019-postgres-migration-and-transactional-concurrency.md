# ADR 0019: Postgres Migration And Transactional Concurrency

## Status

Accepted

## Context

By Step 20, V2_SPRING had a strong single-node control plane, but the primary
store semantics were still effectively SQLite-first.

That was sufficient for local development and bounded founder/operator loops,
but it was no longer a healthy foundation for:

- multi-writer claim / renew / reclaim traffic
- row-level ownership semantics around execution leases
- versioned schema evolution for a long-lived operational ledger

Step 21 introduces the first Postgres-oriented slice so the storage layer starts
matching the concurrency model already designed in Steps 17-20.

## Decision

We adopt the following Step 21 baseline:

1. PostgreSQL becomes the intended primary store for multi-writer operation.
2. Execution-claim hot paths gain dialect-aware row-lock helpers so Postgres can
   enforce claim ownership through `FOR UPDATE` semantics.
3. JSON-heavy ledger payloads use a PostgreSQL JSONB variant while preserving
   SQLite compatibility for local development.
4. Alembic is introduced as the official schema-versioning path.
5. Lease / claim / reclaim paths remain the first migration target; LangGraph
   persistence is deferred until after core ledger semantics are stable on
   Postgres.

## Consequences

### Positive

- lease and fencing logic now has a clearer storage contract on Postgres
- audit payloads are better positioned for indexed JSON queries on Postgres
- schema evolution has a versioned migration baseline instead of relying only on
  implicit ORM bootstrap
- Step 21 narrows the gap between current single-node behavior and future
  multi-agent execution

### Negative

- the repository now carries Alembic scaffolding that must be maintained
- row-locking paths add dialect-specific behavior to the store
- connection pool sizing and lock contention still need runtime observation and
  follow-on hardening

## Follow-on

- keep `RISK-0055`, `RISK-0056`, and `RISK-0057` open as mitigating until
  Postgres-backed runtime behavior is proven end-to-end
- keep planner/runtime side-effect risks out of scope until networked runtimes
  are intentionally opened
