# ADR 0009: Production Planner Transport Seam

## Status

Accepted

## Context

Step 10-a proved the planner slot with a scripted transport.
Step 10-b completed the founder reply lane.

The next gap was production reality:

- real network latency
- provider-specific structured-output behavior
- token accounting
- retry / timeout / cancellation handling
- sanitization and bounded context windowing

If we connected a real LLM directly to the planner core, provider exceptions and
SDK semantics would leak across the control plane boundary.

## Decision

We introduce a provider-agnostic `StructuredPlannerTransport` seam and keep all
provider-specific behavior at the adapter edge.

The first production implementation is **OpenAI-first**, but not
OpenAI-shaped in the core.

Rules:

- the planner core talks only to `StructuredTransportResponse`
- provider SDK exceptions are translated into internal typed transport errors
- prompt bodies are sanitized before transport invocation
- raw prompt/response bodies are not persisted by default; prompt hashes and
  transport telemetry are recorded instead
- prompt payloads are truncated before transport invocation when the bounded
  context window becomes too large
- provider/network retry is handled inside the transport adapter and remains
  separate from planner phase budget accounting
- a second provider path may be added behind the same seam without changing
  planner core types
- local cancellation is normalized into typed transport errors and recorded as
  bounded orphan-risk audit evidence rather than being treated as a silent drop

## Consequences

### Positive

- provider/network instability stays outside the planner core
- transport telemetry becomes replayable without storing raw prompt bodies
- adding a second provider later does not require changing planner core types
- single-provider-first implementation is still fast enough to deliver usable
  production hardening now

### Negative

- the first concrete adapter still has vendor-specific behavior that must be
  watched for lock-in
- additional providers still need their own concrete translation layers and
  policy tuning
- cancellation/orphan behavior is not fully solved by foreground CLI handling
- prompt truncation may trade completeness for bounded cost and latency

## Follow-up

- Step 10-c implements the first concrete OpenAI transport and telemetry path
- the seam is now validated by both OpenAI-style JSON schema transport and an
  Anthropic-style tool-use transport path in tests
- cancellation/orphan semantics remain an explicit risk before scale
