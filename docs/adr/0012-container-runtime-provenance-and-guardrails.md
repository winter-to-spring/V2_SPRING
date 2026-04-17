# ADR 0012: Container Runtime Provenance And Guardrails

## Status
Accepted

## Context

Step 13 introduced a containerized worker runtime, but left three trust gaps:

- mutable image tags weakened deterministic replay
- log collection could still hide root cause or pressure the host
- container capability claims were not yet checked against a shared manifest

Step 14 closes those gaps without introducing live registry dependency into the
dispatch path.

## Decision

We adopt the following runtime provenance and guardrail policy:

1. Container runtime metadata is stored in a repo-managed registry artifact.
   - Current path: `infra/worker_manifest.json`
   - Dispatch/preflight must not depend on live registry queries.
2. Worker base images are pinned by immutable digest.
3. Receipts record runtime provenance.
   - image tag
   - resolved local image digest
   - metadata registry path
   - metadata registry schema version
   - metadata registry checksum
4. Log hygiene is bounded and diagnostic-first.
   - sandwich capture (`head + tail`) replaces tail-only capture
   - oversized logs return bounded evidence instead of full raw copy-out
5. Capability preflight is static-first with selective dynamic escalation.
   - static manifest checks are always applied
   - selected lanes may run a lightweight dynamic admission check
6. Compatibility mismatch is a typed refusal, not a vague runtime crash.

## Consequences

### Positive

- replay can distinguish runtime identity more precisely
- dispatch remains available even when external registries are unavailable
- operator diagnostics remain bounded without going blind to startup failures
- capability mismatch becomes a governed outcome rather than a confusing crash

### Negative

- metadata registry becomes a new managed control-plane artifact
- routing and execution now depend on manifest consistency across environments
- selective dynamic checks add a small amount of runtime overhead

## Follow-up

- `RISK-0036` remains open for image bloat / cold-pull latency
- `RISK-0039` remains mitigating until broader capability lanes accumulate more
  observed-runtime trust signals
