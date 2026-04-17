# Step 12-a: Execution Plane Routing Policy

## What This Slice Adds

Step 12-a introduces the first deterministic bridge between the planner-facing
control plane and future execution runtimes.

This slice adds:

- typed execution requirements
- typed execution runtime taxonomy
- pure routing policy evaluation via `route_task(...)`
- dispatcher-side sanity checks and capability ceilings
- typed routing refusals instead of exception-driven control flow
- founder/operator route inspection via `v2-spring task route`
- replayable routing audit observations

## Key Runtime Rules

- planners declare requirements, not concrete runtime names
- dispatcher policy is skeptical and may downshift obvious complexity inflation
- founder/system limits cap what the planner may request
- no matching runtime yields a typed `RoutingRefusalReceipt`
- routing policy remains pure and side-effect free
- routing inspection only considers currently legal execution lanes

## Why Explicit Rules First

Routing is one of the most sensitive governance boundaries in the system.

We deliberately start with explicit rule branches rather than a scoring
registry because:

- the runtime matrix is still small
- auditability matters more than dynamic cleverness
- explicit branches are easy to unit-test
- refusal paths stay understandable during founder review

This creates intentional technical debt, tracked separately as `RISK-0026`.

## Current Routing Matrix

### `bounded_local`

Used when the request is:

- low complexity
- offline
- read-only
- artifact-only
- not asking for multi-file context

### `isolated_worker`

Used when the request exceeds the cheap bounded lane but still fits the current
proof boundary:

- no network
- complexity at or below current allowed cap after normalization
- output kind still fits bounded worker proof expectations

## Refusal Philosophy

Routing refusals are not crashes. They are expected governance outcomes.

Examples:

- no currently legal execution lane
- requested capability exceeds system policy
- no registered runtime can satisfy normalized requirements safely

These outcomes are returned as typed receipts so they can flow naturally into
audit trails, founder surfaces, and later planner failure reports.

## Risks Touched In This Slice

- `RISK-0005`: partially mitigated through explicit current-state routing
  inspection and later dispatch anchor planning
- `RISK-0022`: intentionally deferred by keeping Step 12-a single-lane and
  non-distributed
- `RISK-0026`: opened intentionally as a later hardening concern

## Feedback Incorporated

- Routing feedback strongly favored requirement-based dispatch over exposing
  runtime names to the planner.
- Additional review pressure required the dispatcher to normalize and distrust
  planner requirements instead of accepting them at face value.
- That is why refusals became typed governance outcomes and the first routing
  implementation stayed explicit-rule based instead of scoring-driven.
