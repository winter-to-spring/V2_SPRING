# Risk ID: RISK-0026
Title: Explicit dispatcher rules may sprawl into a hard-to-audit routing blob as runtimes grow
Class: Later Hardening
Status: Open
Owner: Execution plane / Dispatcher
Observed In: Step 12-a routing policy planning

## Description

Step 12-a intentionally starts with explicit rule branches and named guard
functions instead of an opaque scoring registry.

That is the right choice for initial control and auditability, but as more
execution runtimes and requirement dimensions are added, those explicit rules
may grow into a large routing blob that becomes difficult to reason about.

## Impact

- routing behavior becomes hard to audit or change safely
- new runtime additions may require touching too many conditions
- policy conflicts become harder to spot in code review

## Why This Matters

The dispatcher is becoming one of the most sensitive control-plane boundaries.

If its rule set becomes sprawling and implicit, future execution-plane changes
can accidentally reopen safety or cost leaks.

## Suggested Mitigation

- start with explicit rule branches for Step 12-a
- keep routing policy in small named guard functions and compact policy tables
- add narrow tests for every routing branch
- only consider scoring/registry generalization after a stable runtime matrix
  exists

## Capability Gate
- Capability: expanding execution runtimes beyond the initial Step 12 proof
- Gate mode: Later Hardening
- Blocked until: routing rules remain auditable as new runtimes are added

## Issue Link
- GitHub Issue: #28

## Doc Links
- ADR: docs/adr/0010-execution-plane-routing-policy.md
- Design note: docs/implementation-notes/STEP_12A_EXECUTION_PLANE_ROUTING_POLICY.md

## Exit Criteria

- routing rules remain compact and testable as runtime coverage expands
- a future generalization path exists without weakening auditability

## Last Updated
- 2026-04-17
