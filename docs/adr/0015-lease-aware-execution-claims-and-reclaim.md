# ADR 0015: Lease-aware execution claims and pessimistic reclaim

## Status

Accepted

## Context

By Step 16, V2_SPRING could dispatch increasingly capable workers, but the
system still lacked a typed ownership model for in-flight execution.

That left three gaps:

- competing workers could contend on the same run without a shared claim model
- approval-sensitive mutations could race with live execution
- expired or orphaned executions could remain ambiguous unless they were
  explicitly reclaimed and audited

The next capability slice needed to answer:

- who owns this execution lane right now
- until when that ownership remains valid
- what happens when ownership expires or becomes orphaned

## Decision

We introduce a lease-aware execution claim model at the control-plane layer.

The model includes:

- one execution claim per run
- typed claim lifecycle:
  - `ACTIVE`
  - `RELEASED`
  - `RECLAIMED`
  - `EXPIRED` reserved for future use
- lease metadata:
  - owner
  - runtime
  - lease token
  - acquired / heartbeat / expiry timestamps
- lease-aware guards on approval-sensitive mutation lanes
- claim lifecycle visibility in snapshot, progress surface, replay, and audit

We also adopt a **pessimistic reclaim** policy.

- lease TTL includes a small slack window
- once expiry is observed, the old owner is no longer trusted
- reclaim attempts runtime-specific hard fencing before ownership is reopened
- late results are not accepted after reclaim

## Consequences

### Positive

- competing dispatch becomes a typed refusal instead of an implicit race
- approval/founder mutations cannot silently interleave with live execution
- expired claims become reclaimable and founder-visible
- reclaim outcomes are recorded as explicit audit evidence

### Negative

- lease bookkeeping increases runtime/state complexity
- TTL design becomes a governance surface in its own right
- stronger atomic claim semantics and heartbeat policy may still need later
  hardening before broader multi-worker scale

## Follow-up

- Step 17 resolves the current single-node/current-runtime concurrency gap
- stronger atomic claim semantics remain tracked under `RISK-0047`
- longer-lived/adaptive lease policy remains tracked under `RISK-0046`
- reclaim side-effect fencing remains tracked under `RISK-0048`
