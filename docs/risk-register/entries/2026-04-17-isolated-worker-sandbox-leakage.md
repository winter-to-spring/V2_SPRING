# Risk ID: RISK-0023
Title: Isolated worker proof may leak secrets or main workspace access if isolation is only logical
Class: Before Next Phase
Status: Open
Owner: Execution plane / Sandbox adapter
Observed In: Step 12-b isolated worker proof planning

## Description

If Step 12-b treats "isolated worker" as a simple subdirectory or loose
worktree without tighter execution boundaries, the worker may still:

- traverse upward into the main workspace
- read copied `.env` material or ambient local secrets
- inherit environment variables that should never leave the control plane

That would turn the worker proof into a misleading sandbox illusion rather than
real bounded execution.

## Impact

- secrets or local credentials may leak into worker runtime
- worker may mutate files outside its intended scope
- control-plane immutability assumptions become false in practice

## Why This Matters

Execution-plane safety is one of the main reasons V2_SPRING can eventually use
fast bypass-style workers without turning into V1.

If Step 12-b does not enforce a credible execution boundary, the proof is not a
proof.

## Suggested Mitigation

- run workers inside a dedicated task directory or stronger jail boundary
- do not copy `.env` or local secret files into worker scope
- restrict worker-visible environment to an explicit allowlist
- split stronger OS/container isolation into a separate tracked risk so the
  Step 12-b proof can stay small without hiding the remaining exposure

## Capability Gate
- Capability: isolated worker proof (Step 12-b)
- Gate mode: Before Next Phase
- Blocked until: worker execution boundary is strong enough that workspace and
  secret leakage are not trivial

## Issue Link
- GitHub Issue: #29

## Doc Links
- ADR:
- Design note: docs/issues/STEP_12B_ISOLATED_WORKER_PROOF.md

## Exit Criteria

- worker runtime cannot directly access the parent workspace by default
- `.env` and comparable secret surfaces are excluded from worker scope
- worker-visible environment is bounded and documented

## Last Updated
- 2026-04-17
