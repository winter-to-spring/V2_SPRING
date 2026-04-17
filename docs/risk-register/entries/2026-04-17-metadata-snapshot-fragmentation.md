# Risk ID: RISK-0037
Title: ~~Local metadata snapshots may drift across environments and make routing decisions non-deterministic~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Metadata registry
Observed In: Step 14 provenance and preflight planning

## Description

Step 14 intentionally avoids live registry lookups during dispatch by relying on
local metadata snapshots for image provenance and capability manifests.

That improves resilience, but it introduces a new determinism risk: if one
developer machine, CI node, or server has a different local snapshot revision
than another, the same execution requirements may route differently in each
environment.

## Impact

- routing decisions can diverge across environments
- replay/debugging loses trust because "same request" may not mean "same runtime"
- capability gating can become inconsistent between development and production

## Why This Matters

V2_SPRING only benefits from local metadata snapshots if the snapshot itself is
treated as shared, versioned control-plane data rather than private machine
state.

## Suggested Mitigation

- introduce a versioned metadata registry artifact in-repo
- store that registry as a repo-managed JSON/YAML file rather than a mutable DB
  table
- enforce checksum/version visibility in dispatch and replay
- fail closed or refuse routing when required registry metadata is missing or
  incompatible

Current resolution:

- metadata now lives in a repo-managed registry artifact:
  - `infra/worker_manifest.json`
- the runtime records registry path, schema version, and checksum in receipts
- runtime provenance no longer depends on mutable per-host DB state

## Capability Gate
- Capability: Step 14 runtime provenance and capability preflight
- Gate mode: Before Next Phase
- Blocked until: local metadata snapshots are globally versioned and deterministic

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR: ../../adr/0012-container-runtime-provenance-and-guardrails.md
- Design note: ../../implementation-notes/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## Exit Criteria

- metadata registry is versioned and shared across environments
- metadata registry lives as a repo-managed JSON/YAML artifact under version
  control
- routing uses deterministic registry identity rather than ad-hoc local state
- replay can show which registry snapshot was used for a routing decision

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 14)
