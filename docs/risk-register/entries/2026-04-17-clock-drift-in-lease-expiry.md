# Risk ID: RISK-0050
Title: ~~Lease expiry may become non-deterministic when worker clocks drift from store/server time~~
Class: Before Scale
Status: Resolved
Owner: Store / scheduler time authority
Observed In: Step 18 lease renewal design

## Description

If workers or containers trust their own local clock for expiry decisions,
small clock skew can turn into spurious renewals, premature reclaim, or stale
result rejection.

That would make lease ownership depend on time drift rather than control-plane
truth.

## Impact

- healthy workers could be reclaimed unnecessarily
- stale workers could believe they still own execution longer than the store
  does
- founder/operator trust in lease semantics would erode

## Why This Matters

Lease ownership is only believable if every participant agrees on one time
authority.

V2_SPRING cannot afford "my clock said I still owned it" as an explanation for
state drift.

## Suggested Mitigation

- do not trust worker local clocks for expiry or renewal truth
- compute renewal/expiry from central store/server time only
- keep workers limited to lease token / fencing token / execution context proofs

Current resolution:

- Step 18 treats store/server time as the only expiry truth
- workers request renewal but do not authoritatively extend their own lease
- stale-result and renewal checks both compare against the current central claim
  view

## Capability Gate
- Capability: lease-aware execution across container/worker boundaries
- Gate mode: Before Scale
- Blocked until: lease expiry no longer depends on per-worker local clocks

## Issue Link
- GitHub Issue: #43

## Doc Links
- ADR: ../../adr/0016-lease-renewal-fencing-and-stale-result-rejection.md
- Design note: ../../implementation-notes/STEP_18_LEASE_RENEWAL_AND_FENCED_RECLAIM_HARDENING.md

## Exit Criteria

- expiry truth is centralized in the store/server clock
- worker clocks are not used for authoritative lease decisions
- renewal and stale-result checks both rely on the same central claim state

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 18)
