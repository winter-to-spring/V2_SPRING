# Risk ID: RISK-0049
Title: Lease renewal heartbeats may amplify control-plane write load as worker count grows
Class: Before Scale
Status: Mitigating
Owner: Execution scheduler / lease heartbeat policy
Observed In: Step 18 lease renewal hardening

## Description

Lease renewal solves the fixed-TTL starvation problem, but it introduces a new
operational risk: renewal traffic itself can become expensive.

If a larger fleet of workers renews too frequently, the ledger/store may spend
more effort processing heartbeat writes than handling real execution outcomes.

## Impact

- write amplification can erode control-plane throughput
- founder/operator surfaces may be flooded with low-signal renewal churn
- renewal traffic can become a hidden scale tax before the actual workload does

## Why This Matters

V2_SPRING is trying to make ownership explicit, not turn "I'm still alive"
signals into the dominant workload.

The lease model has to remain operationally cheaper than the work it governs.

## Suggested Mitigation

- renew only when remaining TTL falls below a bounded threshold
- avoid per-heartbeat writes while the lease is still healthy
- consider adaptive intervals or batched renewal for larger worker fleets
- keep renewal events founder-visible enough for audit without turning them into
  high-noise telemetry

Current mitigation:

- Step 18 adds thresholded renewal rather than unconditional heartbeat writes
- healthy leases do not emit renewal events
- store/server time remains the single source of truth for expiry

## Capability Gate
- Capability: larger worker fleets / background executors / higher-frequency
  lease lanes
- Gate mode: Before Scale
- Blocked until: heartbeat traffic stays bounded as agent count and worker
  concurrency increase

## Issue Link
- GitHub Issue: #43

## Doc Links
- ADR: ../../adr/0016-lease-renewal-fencing-and-stale-result-rejection.md
- Design note: ../../implementation-notes/STEP_18_LEASE_RENEWAL_AND_FENCED_RECLAIM_HARDENING.md

## Exit Criteria

- renewal traffic remains sublinear relative to worker count in normal operation
- healthy workers do not generate unnecessary heartbeat writes
- larger worker fleets have either adaptive renewal cadence or batching

## Last Updated
- 2026-04-17
