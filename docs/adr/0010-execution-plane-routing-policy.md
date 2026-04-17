# ADR-0010: Execution Plane Routing Policy

## Status

Accepted

## Context

Step 12 opens the execution plane. From this point on, the control plane must
decide which execution runtime should handle a task without leaking runtime
taxonomy into planner prompts or letting workers self-select their own lane.

We want:

- deterministic control-plane routing
- planner/runtime decoupling
- founder-visible routing rationale
- safe refusal when a route is not legal or not fulfillable
- a narrow seam that can later grow to isolated workers and multi-runtime
  execution without turning routing into opaque magic

## Decision

We adopt **requirements-based routing** with an explicit dispatcher.

### Planner responsibilities

The planner declares **execution requirements**, not runtime names.

Examples:

- `task_complexity`
- `needs_isolation`
- `requires_network`
- `needs_multi_file_context`
- `write_scope`
- `expected_output_kind`

The planner must not emit concrete runtime identifiers such as
`isolated_worker` or `crewai_team`.

### Dispatcher responsibilities

The Python control plane owns runtime selection.

It must:

- normalize obviously inflated requirements
- enforce founder/system capability ceilings
- map requirements to a concrete runtime through explicit policy branches
- return a typed refusal when no safe runtime exists
- remain a **pure function** at its core

The dispatcher is intentionally skeptical. Planner requirements are hints, not
authority.

### Initial implementation shape

The initial routing policy uses **explicit rule branches and named guard
functions**, not a scoring registry.

This keeps routing auditable and easy to test while the runtime matrix is still
small.

### Refusal semantics

Unfulfillable routing is a domain outcome, not an exception.

Routing therefore returns:

- `RoutingDecision`, or
- `RoutingRefusalReceipt`

Exceptions are reserved for actual programmer/configuration faults rather than
expected governance outcomes.

### Freshness boundary

Routing inspection must use current snapshot/action state and must not silently
route work from a stale or blocked lane. Later dispatch and intake slices will
extend this with stronger base-context anchors for conflict-aware worker output
handling.

## Consequences

### Benefits

- planner prompts stay infra-agnostic
- runtime additions do not require prompt churn
- routing decisions are replayable and founder-readable
- refusal paths remain inside the normal FSM/audit flow
- routing logic is easy to test in isolation

### Costs

- explicit rules can sprawl as runtimes grow
- system limits must be maintained carefully
- some future runtime richness is deferred until the dispatcher matrix expands

## Related Risks

- `RISK-0005` RunSnapshot staleness under concurrent writes
- `RISK-0022` multi-worker approval concurrency
- `RISK-0026` routing policy sprawl
