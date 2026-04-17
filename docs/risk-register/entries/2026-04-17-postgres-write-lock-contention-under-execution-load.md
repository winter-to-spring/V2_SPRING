# Risk ID: RISK-0057
Title: Postgres write lock contention may reduce execution throughput under claim and renewal load
Class: Before Next Phase
Status: Mitigating
Owner: Storage / Execution plane
Observed In: Step 21 planning

## Description

Postgres will give V2_SPRING stronger transactional guarantees, but the lease
and audit design can still become inefficient if claims, renewals, and event
writes contend on the same rows or indexes too aggressively.

This is especially likely once heartbeat/renew traffic and execution-claim
updates are mixed with normal audit writes.

## Impact

- claim acquisition latency may spike under worker concurrency
- healthy renewals may slow down unrelated founder/operator flows
- the control plane may become correct but operationally sluggish

## Why This Matters

Correctness is the first goal of Step 21, but we also need a path that remains
usable once multi-writer execution opens wider.

## Suggested Mitigation

- keep thresholded renewal semantics from Step 19
- design indexes for claim lookup, expiry, and active-claim checks explicitly
- validate high-contention paths with targeted concurrency tests
- prefer short transactions and narrow lock scope on claim/reclaim hot paths

Current mitigation:

- Step 21 adds Postgres-aware row locking on claim acquisition, renewal, and
  reclaim paths
- execution-claim tables now carry explicit Postgres-friendly indexes for
  status/expiry and runtime/status lookups
- targeted regression tests now cover the generated locking SQL and JSONB
  variants used by the ledger

## Capability Gate
- Capability: multi-writer execution with Postgres as the primary store
- Gate mode: Before Next Phase
- Blocked until: claim/renew/reclaim paths demonstrate bounded contention under
  expected concurrency

## Issue Link
- GitHub Issue: #47

## Doc Links
- ADR: ../../adr/0019-postgres-migration-and-transactional-concurrency.md
- Design note: ../../issues/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md

## Exit Criteria

- claim and renewal hot paths have explicit index/transaction strategy
- concurrency regression tests show acceptable contention behavior

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating in Step 21)
