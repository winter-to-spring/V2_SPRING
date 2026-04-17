# Risk ID: RISK-0033
Title: ~~Containerized worker image tags may drift and break deterministic replay without digest-pinned provenance~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Container runtime
Observed In: Step 13 containerized worker proof

## Description

Step 13 proves the containerized worker runtime with a static image tag:

- `v2-spring/container-worker-proof:static-v1`

That was stable enough for the initial proof, but it was not strong enough to
guarantee deterministic replay across time.

If the base image or the tagged worker image is rebuilt differently later, the
same logical task may run inside a materially different environment even though
the tag looks unchanged.

## Impact

- replay can become non-deterministic across machines or dates
- debugging gets harder because "same image tag" no longer means same runtime
- future worker capability expansion could inherit silent supply-chain drift

## Why This Matters

V2_SPRING's execution plane is only trustworthy if the runtime identity is as
replayable as the patch / artifact / receipt contract around it.

Containerization without image provenance is safer than soft isolation, but it
is still not strong enough for long-lived deterministic execution claims.

## Suggested Mitigation

- pin base images by immutable digest instead of mutable tags
- record resolved image digest in the containerized worker receipt
- avoid live registry queries during dispatch; rely on a local metadata snapshot
  of image provenance instead
- make runtime provenance visible in replay/progress surfaces when needed
- avoid `latest` or mutable upstream tags in worker image definitions

Current resolution:

- the worker Dockerfile now pins the base image by immutable digest
- the runtime loads provenance from a repo-managed metadata registry artifact
- receipts now record:
  - runtime image tag
  - resolved local image digest
  - metadata registry path
  - metadata registry schema version
  - metadata registry checksum

## Capability Gate
- Capability: broader containerized worker capability expansion
- Gate mode: Before Next Phase
- Blocked until: containerized worker runtime uses digest-pinned image provenance,
  receipts capture the resolved image identity, and dispatch no longer depends on
  live registry availability

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR: ../../adr/0012-container-runtime-provenance-and-guardrails.md
- Design note: ../../implementation-notes/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## Exit Criteria

- container worker images are pinned by digest or equivalent immutable identity
- receipts store the resolved image digest
- replay can distinguish image revisions even when logical runtime names stay the
  same

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 14)
