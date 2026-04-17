# Risk ID: RISK-0036
Title: Container worker image growth may inflate pull latency and erode execution-plane responsiveness
Class: Before Scale
Status: Open
Owner: Execution plane / Worker image strategy
Observed In: Step 14 provenance and capability-preflight planning

## Description

Step 14 correctly keeps the first container runtime on a static image, but that
creates a future pressure point: as more tools and capability manifests are
added, the image may grow into a very large "super image".

At that point the system can remain logically correct while still becoming
operationally sluggish:

- cold start gets slower
- new nodes spend a long time pulling images
- dispatch latency drifts upward even before work begins

## Impact

- execution plane loses its speed advantage
- new environments become slower to recover or scale out
- debugging gets noisier because "runtime is healthy" and "runtime is usable"
  drift apart

## Why This Matters

V2_SPRING should prefer explicit, deterministic runtime policy, but that should
not silently turn into multi-GB worker images without any control point.

This is not a Step 14 blocker for the first proof lane, but it becomes
important before broader worker capability expansion or multi-node rollout.

## Suggested Mitigation

- keep proof/runtime images intentionally narrow
- separate image capability growth from worker contract changes
- consider pre-pulled image pools, layered images, or capability-specific image
  splits before scale
- surface image size and cold-start expectations in runtime ops documentation

## Capability Gate
- Capability: broad containerized worker capability expansion and multi-node use
- Gate mode: Before Scale
- Blocked until: image growth has an explicit strategy so pull latency does not
  undermine execution-plane responsiveness

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR:
- Design note: ../../docs/issues/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## Exit Criteria

- image growth is measured and bounded
- capability expansion does not rely on one unbounded "super image"
- cold-start / pull behavior is understood and operationally acceptable

## Last Updated
- 2026-04-17
