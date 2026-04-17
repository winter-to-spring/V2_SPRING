# Risk ID: RISK-0032
Title: ~~Containerized worker may leave orphan containers behind after interruption or crash~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Reclaim semantics
Observed In: Step 13 containerized worker planning

## Description

If the host process exits unexpectedly or the worker runtime is interrupted at
the wrong moment, stopped or still-running worker containers may remain on the
host.

Without explicit reclaim labels and garbage collection, these containers become
resource leaks and operational noise.

## Impact

- CPU/RAM/disk usage drifts over time
- later dispatches may fail or become confusing
- local and server environments diverge because of hidden orphan containers

## Why This Matters

Step 10-c and Step 12 already treat cancellation/orphans as first-class
operational risks. Containerized execution must meet the same standard instead
of creating a new unmanaged leak surface.

## Suggested Mitigation

- label all worker containers deterministically
- reclaim current containers in all success/failure/timeout paths
- add startup garbage collection for leftover labeled containers

Implemented resolution:

- Step 13 labels proof containers deterministically
- timeout path force-kills the active worker container
- finalize path force-removes the current proof container
- startup garbage collection removes stale labeled proof containers before a new dispatch

## Capability Gate
- Capability: containerized worker proof / repeated dispatch loops
- Gate mode: Before Next Phase
- Blocked until: orphan containers are reclaimed deterministically

## Issue Link
- GitHub Issue: #35

## Doc Links
- ADR: ../../adr/0011-containerized-worker-runtime.md
- Design note: ../../implementation-notes/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md

## Exit Criteria

- worker containers carry deterministic labels
- reclaim path cleans up current containers
- startup GC removes leftover proof containers safely

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 13 reclaim semantics)
