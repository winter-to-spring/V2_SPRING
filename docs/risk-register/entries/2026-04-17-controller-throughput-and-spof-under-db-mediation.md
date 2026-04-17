# Risk ID: RISK-0061
Title: Controller-mediated DB access may become a throughput bottleneck or SPOF
Class: Before Next Phase
Status: Mitigating
Owner: Control plane / Runtime coordination
Observed In: Step 22 controller-boundary hardening

## Description

Controller-mediated DB access is the right trust boundary for V2_SPRING, but it
changes the shape of the bottleneck.

If every worker, reconcile path, or operational query must flow through the
controller, the controller itself can become the narrow waist of the system.

## Impact

- request backlogs may build even when Postgres itself is healthy
- founder/operator UX may feel slow for controller reasons rather than DB reasons
- the system may trade DB safety for a new application-layer bottleneck

## Why This Matters

The controller boundary is strategically correct, but Step 22 should make that
boundary observable and intentionally lightweight, not magical.

## Suggested Mitigation

- keep the controller DB mediation path narrow and purpose-built
- surface whether failures are DB-side or controller-side
- avoid direct worker DB access while measuring controller throughput separately
- defer broader cache/queue layers until evidence shows they are needed

Current mitigation:

- Step 22 makes the controller DB boundary explicit in `v2-spring doctor`
- the same doctor surface now separates lock waiting / pool pressure from the
  application boundary itself
- live contention smoke gives the controller boundary a measurable signal
  instead of leaving throughput concerns hypothetical

## Capability Gate
- Capability: higher-fanout execution traffic through a controller-owned DB boundary
- Gate mode: Before Next Phase
- Blocked until: controller throughput and failure modes are observable under contention smoke

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR: ../../adr/0020-postgres-contention-soak-and-controller-boundary.md
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md
- Design note: ../../implementation-notes/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## Exit Criteria

- controller-only DB mediation has a measurable throughput envelope
- operator surfaces can distinguish controller pressure from DB pressure

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating with Step 22 controller-boundary diagnostics)
