# Risk ID: RISK-0035
Title: ~~Containerized worker capability expansion may fail because runtime dependencies diverge from host assumptions~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Worker capability registry
Observed In: Step 13 containerized worker proof

## Description

The Step 13 proof uses a narrowly scoped worker entrypoint with very small
runtime assumptions. That keeps the proof deterministic, but it also masks a
future risk:

as we expand worker capabilities, the container runtime may not have the same
tools, interpreters, or dependency surface that soft-isolated host execution
implicitly relied on.

The result is a classic "worked on my host" failure mode, now shifted into the
containerized execution plane.

## Impact

- planner can enter replan loops because the worker runtime lacks required tools
- debugging becomes noisy because failures appear as generic runtime errors
- new worker capabilities may be harder to enable safely than the Step 13 proof
  suggests

## Why This Matters

Static-image-first is the right Step 13 choice, but it means capability
expansion needs an explicit compatibility story.

Without a requirement-to-runtime preflight or manifest check, the dispatcher may
route work into a container runtime that was never actually prepared for it.

## Suggested Mitigation

- add a worker runtime capability manifest for tools and dependency assumptions
- perform a preflight compatibility check before dispatching expanded worker
  capabilities
- start with static manifest-based checks and add selective dynamic admission
  checks for higher-risk or more expensive capability lanes
- return typed routing/runtime refusal when requirements exceed the current image
  capability surface
- keep proof-only container lanes distinct from richer capability lanes

Current resolution for the current containerized lane:

- the runtime now loads a repo-managed capability manifest
- dispatch passes typed `ExecutionRequirements` into the runtime
- static manifest compatibility checks run before execution
- selected tools can run a lightweight dynamic admission check
- incompatibility is surfaced as a typed preflight refusal instead of a vague
  crash

## Capability Gate
- Capability: expanded containerized worker toolchains beyond the Step 13 proof
- Gate mode: Before Next Phase
- Blocked until: worker capability dispatch can verify runtime/image compatibility
  before execution starts

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR: ../../adr/0012-container-runtime-provenance-and-guardrails.md
- Design note: ../../implementation-notes/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## Exit Criteria

- containerized worker capabilities declare their runtime assumptions
- dispatcher/runtime performs a compatibility preflight before expanded worker
  execution
- incompatibility produces a typed refusal or failure report instead of a vague
  runtime crash

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved for the current containerized worker lane)
