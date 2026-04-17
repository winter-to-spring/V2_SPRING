# Risk ID: RISK-0048
Title: Reclaim may reopen ownership before old worker side-effects are fully fenced
Class: Before Scale
Status: Mitigating
Owner: Runtime reclaim / execution isolation
Observed In: Step 17 reclaim design

## Description

Reclaim is only safe if the old owner is truly fenced off before a new owner is
allowed to continue.

If reclaim updated only the ledger state while the previous worker still held a
real execution surface, side-effects could overlap and corrupt state.

## Impact

- stale and new workers could both believe they are entitled to continue
- duplicated or overlapping side-effects could leak into the same run
- founder/operator trust in reclaim semantics would erode quickly

## Why This Matters

Step 17 makes reclaim a first-class part of the execution scheduler.

That means reclaim must be more than a bookkeeping event. It has to represent a
real ownership cutoff.

## Suggested Mitigation

- attempt runtime-specific hard reclaim before reopening ownership
- record reclaim as a typed audit event with runtime/fencing outcome
- keep reclaim pessimistic after expiry rather than accepting late results
- expand fencing semantics before opening remote or externally side-effectful
  runtimes

Current mitigation:

- Step 17 attempts hard container reclaim before marking a containerized claim
  reclaimed
- reclaim results are recorded in typed ledger/audit events
- late ownership is not honored after reclaim

## Capability Gate
- Capability: remote or side-effectful runtimes beyond current bounded worker
  proofs
- Gate mode: Before Scale
- Blocked until: reclaim semantics prove that old owners cannot continue
  producing accepted side-effects after ownership is revoked

## Issue Link
- GitHub Issue: #41

## Doc Links
- ADR: ../../adr/0015-lease-aware-execution-claims-and-reclaim.md
- Design note: ../../implementation-notes/STEP_17_EXECUTION_LEASES_AND_ORPHAN_RECONCILIATION.md

## Exit Criteria

- reclaim includes runtime-specific fencing for every opened runtime class
- stale results are deterministically rejected after reclaim
- reclaim tests prove ownership cutoff rather than just state-table updates

## Last Updated
- 2026-04-17
