# Risk ID: RISK-0060
Title: WAL and storage pressure may rise sharply under heartbeat and audit churn
Class: Before Scale
Status: Open
Owner: Storage / Operations
Observed In: Step 22 contention-soak planning

## Description

Even when contention is controlled, frequent renewals and dense audit/event
writes can generate a large amount of Postgres WAL and disk churn.

This is especially relevant for a control plane that values replayability and
fine-grained operational evidence.

## Impact

- disk usage can rise faster than expected
- backup / replication behavior may degrade
- operational recovery can become harder even when the app itself is correct

## Why This Matters

V2_SPRING should not solve control-plane correctness by silently pushing
unsustainable write churn into the storage layer.

## Suggested Mitigation

- keep heartbeat hygiene and thresholded renewal in place
- observe WAL/storage pressure before broadening worker fanout
- define retention or archival policy for high-volume audit data before scale
- treat storage churn as a first-class operational metric, not a surprise

## Capability Gate
- Capability: sustained multi-worker Postgres operations
- Gate mode: Before Scale
- Blocked until: write churn and storage pressure are understood well enough for operational planning

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR:
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## Exit Criteria

- WAL/storage growth patterns are measured under representative churn
- retention or archive expectations exist before wider rollout

## Last Updated
- 2026-04-17
