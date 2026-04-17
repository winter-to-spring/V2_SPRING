# Step 13 - Containerized Worker Runtime

## What Changed

Step 13 moves the execution-plane proof from strengthened soft isolation to a
container-backed runtime while keeping the Step 12 contract intact:

- the worker still returns only `patch / artifact / receipt`
- the worker still does not mutate the main control-plane state directly
- founder review still gates patch application through the strict intake lane

The runtime proof now runs inside a static Docker image and uses explicit
copy-in / copy-out boundaries instead of a live host mount.

## Key Decisions

### Static image first

The first proof uses one static image:

- predictable environment
- easier debugging
- no image-build policy mixed into runtime-contract proof

Dynamic image assembly is intentionally deferred.

### Least-privilege container policy

The proof lane now enforces:

- no Docker socket mount
- no `--privileged`
- `--cap-drop ALL`
- `--security-opt no-new-privileges=true`
- `--network none`

This makes the containerized worker meaningfully different from the Step 12-b
soft-isolation lane.

### Air-gapped workspace transfer

Source code is not live-mounted into the container.

Instead:

1. the host prepares a task-local copied workspace
2. the runtime copies it into the container with `docker cp`
3. the worker runs inside an internal execution workspace
4. the runtime copies the resulting workspace and `/output` back out

That keeps the host workspace outside the worker's live mutation path.

### Ownership normalization

Copied-out files are normalized on the host before intake reads them. This keeps
patch, log, and receipt handoff deterministic even when the container runtime
produces files with container-local ownership semantics.

### Deterministic reclaim

The proof lane now uses:

- hard timeout on `docker wait`
- forced container kill on timeout
- typed timeout receipt
- deterministic labels on worker containers
- startup garbage collection for leftover proof containers

This closes the silent-orphan gap for the proof lane itself.

## Runtime Flow

1. Route a bounded execution request to `containerized_worker`.
2. Ensure the static image exists.
3. Garbage-collect stale labeled proof containers.
4. Copy the staged workspace into the container.
5. Run the worker entrypoint inside the container.
6. Copy `/output` and the mutated execution workspace back out.
7. Normalize copied-out files on the host.
8. Build the unified patch and typed execution receipt.
9. Persist patch/receipt artifacts and replay evidence.

## Founder / Replay Surface

The founder/operator surface now sees containerized execution as a first-class
runtime:

- routing inspection can select `containerized_worker`
- `task dispatch --runtime containerized_worker` exposes the proof lane
- replay stores a patch artifact and a receipt artifact
- receipt metadata includes:
  - image tag
  - workspace transfer mode
  - network mode
  - least-privilege flags
  - ownership normalization result
  - orphan GC count

## Risks Closed Here

- `RISK-0027` OS/container isolation gap for unrestricted bypass readiness
- `RISK-0030` Docker socket / privileged container escape
- `RISK-0031` copied-out artifact ownership mismatch
- `RISK-0032` orphan container garbage-collection gap

## Risks Still Open

- `RISK-0021` planner-provider cancellation/orphan semantics
- `RISK-0022` multi-worker approval concurrency
- `RISK-0025` review fatigue / risk-based auto-apply routing
- `RISK-0026` routing policy sprawl

## Verification

- targeted Step 13 tests cover:
  - successful containerized proof dispatch
  - timeout reclaim
  - CLI JSON surface
- full test suite remains green after the new runtime lane is added

## Feedback Incorporated

- Container hardening feedback required this slice to include least-privilege
  launch rules, ownership normalization, and orphan garbage collection as core
  acceptance criteria instead of optional polish.
- Additional review pushed the design toward static-image, copy-in/copy-out
  execution rather than live host mounts.
- The result is a stricter but more replayable container runtime boundary.
