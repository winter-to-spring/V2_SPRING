# Step 10-c: Production Planner Transport Hardening

## What This Slice Adds

Step 10-c turns the scripted planner proof path into a production-ready
transport seam without pushing provider specifics into the control-plane core.

This slice adds:

- a provider-agnostic `StructuredPlannerTransport` seam
- one first concrete provider: `OpenAIStructuredPlannerTransport`
- typed transport telemetry via `PlannerTransportAuditView`
- internal transport error normalization and bounded retry
- prompt sanitization plus bounded context truncation
- CLI support for `--provider scripted|openai`
- replayable transport audit observations for both success and failure paths

## Key Runtime Rules

- planner/provider failures are separated from planner governance failures
- provider/network retries happen inside the transport adapter and do **not**
  consume planner phase budget directly
- structured-output parse failures still count as planner adapter failures and
  continue to follow bounded governance
- production prompt payloads are sanitized before leaving the process
- prompt hashes and token usage are recorded instead of raw prompt bodies
- context is truncated before transport invocation when the serialized planner
  window grows too large

## Why OpenAI First But Not OpenAI Everywhere

The first production adapter uses OpenAI structured output because it gives us a
stable place to harden:

- schema enforcement
- timeout / retry behavior
- token usage telemetry
- refusal / malformed output handling

But the core does **not** depend on OpenAI SDK types.

The translation boundary lives at the adapter edge:

- the core sees `StructuredTransportResponse`
- the CLI sees `PlannerTransportAuditView`
- provider exceptions are translated into internal typed transport errors

## Risks Touched In This Slice

- `RISK-0015`: structured failure report fidelity
- `RISK-0019`: provider schema lock-in
- `RISK-0020`: provider error normalization leak
- `RISK-0021`: local cancellation / orphan cost

`RISK-0020` is resolved here.

`RISK-0019` is resolved for the current transport seam.

The planner core now runs unchanged against:

- OpenAI-style strict JSON schema transport
- Anthropic-style tool-use transport

Both providers are translated at the adapter edge into the same
`StructuredTransportResponse` and `PlannerTransportAuditView` shapes.

`RISK-0021` is now mitigating rather than fully open.

Current cancellation guardrails:

- local transport cancellation is normalized into a typed `cancelled` transport
  error
- audit observations now record:
  - `timeout_seconds`
  - `orphan_risk_possible`
  - `cancellation_scope=local_cli_only`
  - a bounded reinvocation hint

The risk remains because this is still foreground CLI cancellation, not true
provider-side request abort or worker-safe cancellation.
