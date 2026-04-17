# Risk ID: RISK-0027
Title: Soft-isolated worker proof lacks OS/container-level isolation and cannot be treated as unrestricted bypass safety
Class: Before Scale
Status: Open
Owner: Execution plane / Sandbox runtime
Observed In: Step 12-b isolated worker proof planning

## Description

Step 12-b intentionally starts with strengthened soft isolation:

- `subprocess`
- task-local working directory
- environment allowlist
- secret file non-copy
- bounded receipts

That is enough to prove the execution-plane contract, but it is not the same as
real OS/container isolation.

Without Docker/E2B/chroot/cgroup-grade boundaries, a sufficiently bad worker
process may still:

- attempt path traversal outside the intended task directory
- consume too much host memory or CPU
- access host-local network surfaces that should not be reachable

## Impact

- unrestricted bypass workers would be unsafe to open broadly
- host resource exhaustion could still affect the control plane
- "isolated worker" could be mistaken for stronger security than actually exists

## Why This Matters

The Step 12-b proof is about contract correctness, not final sandbox security.

If we fail to keep that distinction explicit, later teams may assume the worker
runtime is safe for arbitrary high-speed bypass execution before the isolation
foundation is actually ready.

## Suggested Mitigation

- keep Step 12-b narrowly scoped as strengthened soft isolation proof
- document that OS/container isolation is still absent
- require stronger isolation before enabling unrestricted bypass workers or
  broader execution fan-out
- later add container/cgroup-backed isolation and resource ceilings

## Capability Gate
- Capability: broad/unrestricted bypass-style worker execution
- Gate mode: Before Scale
- Blocked until: worker runtime has credible OS/container-level isolation and
  host resource ceilings

## Issue Link
- GitHub Issue: #29

## Doc Links
- ADR:
- Design note: docs/issues/STEP_12B_ISOLATED_WORKER_PROOF.md

## Exit Criteria

- worker runtime is backed by stronger OS/container isolation
- host resource ceilings are enforced
- unrestricted bypass execution is no longer relying on soft isolation alone

## Last Updated
- 2026-04-17
