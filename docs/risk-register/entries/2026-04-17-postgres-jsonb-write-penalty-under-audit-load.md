# Risk ID: RISK-0059
Title: JSONB-heavy ledger writes may amplify Postgres write cost under audit load
Class: Before Scale
Status: Open
Owner: Storage / Audit ledger
Observed In: Step 22 contention-soak planning

## Description

V2_SPRING uses flexible JSON payloads for parts of the ledger and replay path.
That flexibility is useful, but under heavier write volume it can become
expensive.

If JSONB payloads accumulate broad indexes or are rewritten too often on hot
paths, the cost of each write rises even before lock contention becomes the
dominant bottleneck.

## Impact

- heartbeat/audit write latency may drift upward
- disk I/O and index maintenance can erode throughput
- Postgres can remain logically correct while operationally sluggish

## Why This Matters

Step 22 focuses on contention and controller trust boundaries, but it should
not hide a slower storage penalty that will surface as scale grows.

## Suggested Mitigation

- avoid indexing JSONB fields that are not queried frequently
- keep hot-path write tables lean where possible
- measure whether audit JSON payloads, rather than lock order alone, drive latency
- split ultra-hot operational writes from richer replay payloads if evidence demands it

## Capability Gate
- Capability: higher-volume audit/event traffic on Postgres
- Gate mode: Before Scale
- Blocked until: JSONB write overhead is understood and bounded under expected event load

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR:
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## Exit Criteria

- JSONB write cost is measured under realistic audit volume
- hot-path tables are not paying unnecessary index/update penalties

## Last Updated
- 2026-04-17
