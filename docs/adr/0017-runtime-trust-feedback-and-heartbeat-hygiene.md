# ADR 0017: Runtime Trust Feedback And Heartbeat Hygiene

## Status

Accepted

## Context

Step 18 closed lease ownership and fenced reclaim at the claim layer, but two
operational gaps remained:

- static worker manifests could still drift away from actual runtime behavior
- lease renewal could still create unnecessary write churn as worker counts grow

V2_SPRING needs to keep its default path deterministic and cheap, while still
reacting when real runtime evidence contradicts declared capability.

## Decision

We add a runtime trust layer and tighter renewal hygiene with the following
rules:

1. Containerized runtime trust is tracked centrally in the ledger as typed
   state.
2. Static manifest preflight remains the default path.
3. A runtime is promoted to dynamic preflight only after **three consecutive**
   capability mismatches.
4. A dynamically promoted runtime returns to static-first mode after **two
   successful** dynamic-preflight executions.
5. Lease renewal uses store/server time as the only source of truth.
6. Renewal writes are coalesced by a minimum cadence window so "I'm still
   alive" traffic does not write on every heartbeat call.

## Consequences

### Positive

- runtime trust no longer depends only on declared metadata
- noisy one-off failures do not immediately force expensive dynamic checks
- healthy leases avoid unnecessary renewal writes
- founder/operator surfaces can inspect runtime trust degradation directly

### Negative

- runtime trust introduces another small state machine to maintain
- a runtime can still fail a few times before dynamic preflight promotion
- heartbeat cadence now needs ongoing scale observation if worker fleets expand

## Follow-on

- keep `RISK-0051` deferred until networked or side-effectful runtimes open
- revisit richer trust scoring only if explicit strike/recovery rules become
  insufficient
