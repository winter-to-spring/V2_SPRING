# Risk ID: RISK-0058
Title: ~~Postgres multi-table transactional writes may deadlock under contention~~
Class: Before Next Phase
Status: Resolved
Owner: Storage / Execution plane
Observed In: Step 22 contention-soak planning

## Description

Once V2_SPRING starts exercising Postgres under real claim / renew / reclaim /
audit fanout, correctness alone is not enough.

If multiple workers or controller paths take locks in inconsistent order across
the same small set of tables, Postgres can protect integrity while still
producing deadlocks and aborted transactions.

The risk becomes especially sharp when one path updates execution claims first
and another writes audit/event state first inside longer transactions.

## Impact

- some workers may stall or fail despite otherwise healthy infrastructure
- throughput can collapse under load even when connection pools look fine
- founder/operator perception shifts from "slow" to "randomly unhealthy"

## Why This Matters

Step 22 is about proving Postgres is not just available, but orderly under
real contention. Deadlocks are one of the fastest ways to lose that trust.

## Suggested Mitigation

- keep transaction scopes short and explicit
- document and enforce a consistent lock acquisition order
- include deadlock-prone scenarios in the contention smoke harness
- surface lock-wait / deadlock evidence in diagnostics instead of hiding it in logs

Current resolution:

- Step 22 aligns claim mutation hot paths around a more consistent locking
  order: run row first, claim row second
- Step 22 adds a live PostgreSQL contention smoke probe that exercises the
  blocking renew path while operator diagnostics observe lock waits
- `v2-spring doctor` now exposes live lock-wait visibility so deadlock-like
  pressure is no longer opaque

## Capability Gate
- Capability: multi-writer claim/reclaim/audit traffic on Postgres
- Gate mode: Before Next Phase
- Blocked until: contention smoke demonstrates stable locking order without recurring deadlocks

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR: ../../adr/0020-postgres-contention-soak-and-controller-boundary.md
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md
- Design note: ../../implementation-notes/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## Exit Criteria

- hot-path transactional writes follow a consistent locking order
- contention smoke does not show recurring deadlock failures
- operator diagnostics can distinguish deadlock from simple latency

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 22)
