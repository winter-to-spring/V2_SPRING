# Risk ID: RISK-0047
Title: ~~Execution claim acquisition may still depend on store-level serialization without stronger atomic CAS semantics~~
Class: Before Scale
Status: Resolved
Owner: Store / Scheduler coordination
Observed In: Step 17 claim-acquisition design, Step 18 claim hardening

## Description

Step 17 introduces a typed execution claim model, but true concurrent claim
acquisition still depends on the guarantees of the current local store/DB
behavior.

The current implementation started out adequate for the present single-node
substrate, but broader worker scale needed stronger claim semantics than a bare
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

Current resolution:

- Step 17 limits each run to a single claim row
- live-claim conflicts now surface as typed execution-claim refusals
- approval-sensitive mutation lanes are guarded by the same claim view
- Step 18 keeps the unique one-row-per-run contract and upgrades reacquire/update
  to a version-gated compare-and-swap path
- concurrent insert collisions degrade to typed refusal instead of silent
  double-ownership
- fencing tokens are now visible in founder/operator surfaces and result
  acceptance paths

## Capability Gate
- Capability: broader multi-process or cross-host worker contention
- Gate mode: Before Scale
- Blocked until: claim acquisition semantics are explicitly atomic under
  contention, not just operationally serialized in the current local setup

## Issue Link
- GitHub Issue: #43

## Doc Links
- ADR: ../../adr/0016-lease-renewal-fencing-and-stale-result-rejection.md
- Design note: ../../implementation-notes/STEP_18_LEASE_RENEWAL_AND_FENCED_RECLAIM_HARDENING.md

## Exit Criteria

- current-scope claim acquisition uses explicit version-gated compare-and-swap
- insert/update races degrade to typed governance outcomes instead of ambiguous
  ownership
- the control plane can show the active fencing token for founder/operator audit

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 18)
