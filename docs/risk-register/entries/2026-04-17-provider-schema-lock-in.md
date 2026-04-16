# Risk ID: RISK-0019
Title: ~~Single-provider structured output may leak vendor semantics into the core planner transport seam~~
Class: Before Scale
Status: Resolved
Owner: Core / Planner transport
Observed In: Step 10-c production transport design review

## Description

Step 10-c intentionally starts with one concrete provider so we can harden the
production path without building a full multi-model router first.

That is the right delivery choice, but it creates a risk:

- the first provider's structured-output semantics may become the real contract
- later providers may have to emulate OpenAI-specific behavior instead of
  conforming to a provider-neutral transport seam
- the seam may look generic in type signatures while being vendor-shaped in
  practice

## Impact

- adding Claude or another model later becomes more expensive than expected
- transport abstractions become misleading and brittle
- core planner governance may unknowingly depend on one provider's quirks

## Why This Matters

Single-provider-first is healthy only if the adapter edge remains a real
translation boundary.

If the concrete provider leaks through the seam, Step 10-c delivers short-term
speed at the cost of long-term portability.

## Suggested Mitigation

- keep the internal transport interface narrow and provider-agnostic
- translate provider-specific request/response structures at the adapter edge
- avoid letting provider SDK objects cross into the planner core
- document which guarantees belong to the core contract and which belong only to
  the first concrete provider

Current mitigation in `10-c`:

- the core now talks to a provider-agnostic `StructuredPlannerTransport`
- the first concrete adapter is OpenAI-specific, but only at the adapter edge
- provider telemetry is translated into `PlannerTransportAuditView`
- provider/network failures are normalized into internal transport errors before
  they reach CLI governance paths

Current resolution:

- the seam now supports both OpenAI-style strict JSON schema transport and an
  Anthropic-style tool-use transport without changing planner core types
- CLI/provider selection and config remain adapter-edge concerns
- provider-specific request/response translation stays inside concrete transport
  classes
- transport tests prove a second provider path can be exercised behind the same
  `StructuredPlannerTransport` protocol

## Capability Gate
- Capability: second production planner provider / multi-model rollout
- Gate mode: Before Scale
- Blocked until: provider-neutral guarantees are explicit and concrete adapters
  continue to translate provider behavior only at the edge

## Issue Link
- GitHub Issue: #23

## Doc Links
- ADR: ../../adr/0009-production-planner-transport-seam.md
- Design note: ../../implementation-notes/STEP_10C_PRODUCTION_TRANSPORT_HARDENING.md

## Exit Criteria

- the first production provider is fully wrapped behind an internal transport
  seam
- adding a second provider does not require changing planner core types
- the second provider path is proven in tests or production trials without
  rewriting planner core contracts

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved for the current adapter seam)
