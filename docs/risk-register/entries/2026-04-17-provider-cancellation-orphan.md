# Risk ID: RISK-0021
Title: Local CLI cancellation may leave an in-flight provider call orphaned after the terminal exits
Class: Before Scale
Status: Mitigating
Owner: Core / Planner transport
Observed In: Step 10-c production transport hardening

## Description

Step 10-c now normalizes local cancellation into a typed transport error when
Python receives `KeyboardInterrupt`.

That improves replayability and error classification, but it does **not**
guarantee that the upstream provider has actually stopped billing or abandoned
the request.

If a founder interrupts `planner invoke` locally while the provider call is
still in flight, the control plane may stop waiting while the remote provider
continues processing for some amount of time.

## Impact

- local CLI experience says "cancelled" while remote spend may still happen
- repeated interrupts can create confusing audit trails and hidden cost drift
- future background execution may need stronger cancellation semantics than the
  current foreground CLI path

## Why This Matters

The transport seam is now resilient to many network/provider failures, but true
orphan prevention requires request lifecycle control beyond simple CLI signal
handling.

If we expand planner invocation into background workers or long-running founder
surfaces, cancellation semantics must become more explicit.

## Suggested Mitigation

- keep per-call timeout bounded so orphan exposure stays small
- record local cancellation as structured audit evidence
- investigate provider-side idempotency or cancellation handles before scale
- add worker-safe cancellation policy before moving planner transport off the
  foreground CLI

Current mitigation:

- local cancellation is normalized into a typed `PlannerTransportCancelledError`
- cancellation audit observations now include:
  - `timeout_seconds`
  - `orphan_risk_possible`
  - `cancellation_scope=local_cli_only`
  - a bounded reinvocation hint for founders
- Step 20 adds a second reconciliation audit so replay distinguishes:
  - cancellation intent
  - local reconciliation / bounded orphan-risk finalization
- transport tests and CLI tests now cover the cancellation path explicitly

## Capability Gate
- Capability: background planner workers / long-running planner invokes
- Gate mode: Before Scale
- Blocked until: cancellation semantics are explicit enough that local aborts do
  not silently become hidden provider spend

## Issue Link
- GitHub Issue: #23, #46

## Doc Links
- ADR: ../../adr/0009-production-planner-transport-seam.md
- ADR: ../../adr/0018-snapshot-freshness-and-cancellation-reconciliation.md
- Design note: ../../implementation-notes/STEP_10C_PRODUCTION_TRANSPORT_HARDENING.md
- Design note: ../../implementation-notes/STEP_20_SNAPSHOT_FRESHNESS_AND_CANCELLATION_RECONCILIATION.md

## Exit Criteria

- planner invocation supports bounded cancellation semantics beyond local CLI
  interrupts
- long-running or background planner execution can reconcile interrupted
  requests without hidden provider cost

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating)
- 2026-04-17 (Step 20 reconciliation audit)
