# Risk ID: RISK-0046
Title: Lease TTL may starve long-running work or delay reclaim when ownership lasts too long
Class: Before Scale
Status: Mitigating
Owner: Execution scheduler / lease policy
Observed In: Step 17 lease-aware execution claims

## Description

Lease-aware claims solve ownership ambiguity, but TTL design can introduce a
new problem.

If lease TTL is too long, reclaim becomes sluggish and failed owners can block
progress for too long. If TTL is too short, legitimate work may lose ownership
before it finishes.

That creates a starvation/deadlock tradeoff inside the lease model itself.

## Impact

- execution may remain blocked behind stale claims longer than necessary
- legitimate work may be reclaimed too aggressively if TTL is too small
- repeated reclaim/retry loops can waste time and compute budget

## Why This Matters

Step 17 adopts pessimistic reclaim, which is the right safety choice for
V2_SPRING.

That makes TTL quality important: the slack has to be large enough for bounded
work to finish, but small enough that reclaim remains useful.

## Suggested Mitigation

- derive TTL from bounded task timeout instead of using a global static lease
- keep a small reclaim slack inside the lease model itself
- add heartbeat or renewal only when longer-lived runtimes are opened
- consider adaptive TTL once worker classes become more diverse

Current mitigation:

- Step 17 derives lease TTL from task timeout plus bounded slack
- reclaim is pessimistic and founder-visible
- expired claims can be explicitly reconciled instead of silently lingering

## Capability Gate
- Capability: longer-lived workers / background executors / adaptive lease lanes
- Gate mode: Before Scale
- Blocked until: TTL/renewal policy is explicit enough for workers that are no
  longer tightly bounded by local timeout contracts

## Issue Link
- GitHub Issue: #41

## Doc Links
- ADR: ../../adr/0015-lease-aware-execution-claims-and-reclaim.md
- Design note: ../../implementation-notes/STEP_17_EXECUTION_LEASES_AND_ORPHAN_RECONCILIATION.md

## Exit Criteria

- lease TTL is explicit for each execution class
- reclaim does not routinely interrupt legitimate bounded work
- longer-lived runtimes have renewal/heartbeat semantics before they are opened

## Last Updated
- 2026-04-17
