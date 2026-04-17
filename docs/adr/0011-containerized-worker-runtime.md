# ADR-0011: Containerized Worker Runtime Uses Static Images, Air-Gapped Copy-In/Out, and Least-Privilege Launch Policy

## Status

Accepted

## Context

Step 12 proved the execution-plane contract with strengthened soft isolation,
but that lane was not strong enough to support broader bypass-style worker
execution.

To close `RISK-0027`, V2_SPRING needs a worker runtime with real
OS/container-level isolation while preserving the existing execution-plane
contract:

- workers return `patch / artifact / receipt`
- workers do not directly mutate control-plane state
- founder review continues to gate final patch application

## Decision

V2_SPRING will introduce a containerized worker proof lane with the following
constraints:

1. Use a single static worker image first.
2. Transfer workspace data with `docker cp` copy-in / copy-out rather than
   live host mounts.
3. Enforce a least-privilege container launch policy:
   - no Docker socket exposure
   - no `--privileged`
   - no network by default
   - `cap-drop ALL`
   - `no-new-privileges`
4. Normalize copied-out files on the host before intake reads them.
5. Use deterministic labels, timeout reclaim, and startup garbage collection for
   proof-lane containers.

## Consequences

### Positive

- containerized worker execution is now materially safer than Step 12-b
- copy-in / copy-out keeps host workspace mutation boundaries explicit
- replay remains deterministic because patch and receipt artifacts are still the
  source of truth
- the proof lane is testable without introducing a dynamic build pipeline

### Negative

- the first runtime uses one static image, so tool diversity is intentionally
  limited
- copy-in / copy-out is slower than a live mount
- container launch policy is more operationally complex than soft isolation

## Rejected Alternatives

### Live host volume mount

Rejected for the first proof because it weakens isolation boundaries and makes
host mutation semantics less explicit.

### Dynamic image building

Rejected for this slice because image-pipeline complexity is not needed to prove
the runtime contract itself.

### Docker socket or privileged helpers

Rejected because they would undermine the entire purpose of Step 13 by turning
containerized execution into a host escape path.

## Related Risks

- `RISK-0027`
- `RISK-0030`
- `RISK-0031`
- `RISK-0032`

## Related Notes

- `docs/implementation-notes/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md`
