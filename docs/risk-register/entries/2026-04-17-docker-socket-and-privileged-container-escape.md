# Risk ID: RISK-0030
Title: ~~Containerized worker may escape isolation if docker socket or privileged mode is exposed~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Container runtime
Observed In: Step 13 containerized worker planning

## Description

Moving from subprocess isolation to Docker does not automatically make the
runtime safe.

If the worker container is launched with host Docker socket access or privileged
mode, the worker can effectively regain control over the host and other
containers.

## Impact

- host takeover becomes possible despite "containerized" branding
- control-plane integrity can be lost
- `RISK-0027` would remain functionally unresolved

## Why This Matters

Step 13 is meant to prove real execution-plane isolation, not just a stronger
marketing label for the same trust assumptions.

## Suggested Mitigation

- never mount `/var/run/docker.sock` into worker containers
- disallow `--privileged`
- run with least privilege, no-new-privileges, and no network by default
- keep container launch policy explicit and testable

Implemented resolution:

- Step 13 launch path never mounts `docker.sock`
- proof containers do not use `--privileged`
- runtime enforces `--network none`
- runtime enforces `--cap-drop ALL`
- runtime enforces `--security-opt no-new-privileges=true`

## Capability Gate
- Capability: containerized worker proof / unrestricted bypass readiness
- Gate mode: Before Next Phase
- Blocked until: least-privilege container launch policy is enforced

## Issue Link
- GitHub Issue: #35

## Doc Links
- ADR: ../../adr/0011-containerized-worker-runtime.md
- Design note: ../../implementation-notes/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md

## Exit Criteria

- worker launch path cannot expose docker socket
- privileged mode is not used
- least-privilege launch policy is documented and tested

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 13 launch policy)
