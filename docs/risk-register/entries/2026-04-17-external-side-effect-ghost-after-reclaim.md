# Risk ID: RISK-0051
Title: External side-effects may outlive reclaimed lease ownership even when stale results are fenced
Class: Before Scale
Status: Mitigating
Owner: Runtime isolation / external side-effect contracts
Observed In: Step 18 fenced reclaim hardening

## Description

Step 18 can reject stale results after reclaim, but that does not automatically
undo side-effects that already escaped the worker boundary.

If a future runtime can call external APIs, mutate remote systems, or produce
effects outside the local bounded workspace, reclaim may stop accepted results
without fully stopping the external mutation itself.

## Impact

- reclaim could look correct in the ledger while external systems still drift
- duplicate or stale external operations may survive even when internal state is
  fenced
- founder/operator trust could be damaged because the control plane appears more
  authoritative than the external reality actually is

## Why This Matters

Fencing the control plane is necessary, but it is not the same thing as fencing
the world outside the control plane.

The moment V2_SPRING opens runtimes with real external mutation surface, lease
reclaim must extend beyond local result rejection.

## Suggested Mitigation

- pass fencing/idempotency tokens to external systems where possible
- open networked or side-effectful runtimes only with explicit external
  idempotency contracts
- compare pre/post side-effect receipts where a remote system can provide them
- keep current container runtime constrained (`--network none`) until those
  contracts exist

Current mitigation:

- current bounded container workers run with `--network none`
- reclaim remains pessimistic and attempts hard container kill
- stale local results are rejected after reclaim or supersession

## Capability Gate
- Capability: networked runtimes / external API mutation / remote side-effectful
  workers
- Gate mode: Before Scale
- Blocked until: external side-effects can be fenced or deduplicated with the
  same rigor as local result submission

## Issue Link
- GitHub Issue: #43

## Doc Links
- ADR: ../../adr/0016-lease-renewal-fencing-and-stale-result-rejection.md
- Design note: ../../implementation-notes/STEP_18_LEASE_RENEWAL_AND_FENCED_RECLAIM_HARDENING.md

## Exit Criteria

- networked runtimes propagate fencing/idempotency evidence to external systems
- reclaim semantics can explain both local result rejection and external effect
  cutoff
- remote side-effects no longer survive reclaim without explicit audit evidence

## Last Updated
- 2026-04-17
