# Risk ID: RISK-0047
Title: Execution claim acquisition may still depend on store-level serialization without stronger atomic CAS semantics
Class: Before Scale
Status: Mitigating
Owner: Store / Scheduler coordination
Observed In: Step 17 claim-acquisition design

## Description

Step 17 introduces a typed execution claim model, but true concurrent claim
acquisition still depends on the guarantees of the current local store/DB
behavior.

The current implementation is adequate for the present single-node substrate,
but broader worker scale may need stronger atomic claim semantics than
"check-then-write within one store transaction".

## Impact

- competing workers could still depend on DB/driver behavior rather than an
  explicit compare-and-swap contract
- future multi-process expansion may expose claim races that are not visible in
  the current local CLI path
- typed refusal could degrade into lower-level write conflicts if atomicity is
  not formalized further

## Why This Matters

The whole value of Step 17 is that ownership is no longer ambiguous.

If claim acquisition becomes non-deterministic under heavier concurrency, the
lease model loses credibility right where it is supposed to be strongest.

## Suggested Mitigation

- keep one claim row per run
- preserve typed refusal when a live claim already exists
- add stronger version/CAS semantics or DB-native locking before larger
  multi-worker scale
- test claim contention explicitly, not just sequential happy paths

Current mitigation:

- Step 17 limits each run to a single claim row
- live-claim conflicts now surface as typed execution-claim refusals
- approval-sensitive mutation lanes are guarded by the same claim view

## Capability Gate
- Capability: broader multi-process or cross-host worker contention
- Gate mode: Before Scale
- Blocked until: claim acquisition semantics are explicitly atomic under
  contention, not just operationally serialized in the current local setup

## Issue Link
- GitHub Issue: #41

## Doc Links
- ADR: ../../adr/0015-lease-aware-execution-claims-and-reclaim.md
- Design note: ../../implementation-notes/STEP_17_EXECUTION_LEASES_AND_ORPHAN_RECONCILIATION.md

## Exit Criteria

- claim acquisition has explicit atomic/CAS semantics
- contention tests prove deterministic single-owner acquisition
- lower-level write conflicts are translated into typed governance outcomes

## Last Updated
- 2026-04-17
