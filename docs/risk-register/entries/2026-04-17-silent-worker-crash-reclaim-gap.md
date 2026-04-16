# Risk ID: RISK-0024
Title: Isolated worker may crash or hang without a reclaim path, leaving running tasks stuck
Class: Before Next Phase
Status: Open
Owner: Execution plane / Worker runtime
Observed In: Step 12-b isolated worker proof planning

## Description

An isolated worker can die from OOM, internal crash, or runaway loop after the
control plane has already marked the task as dispatched.

Without a hard timeout and reclaim path, the control plane may wait forever for
a receipt that will never arrive.

## Impact

- tasks can remain `running` indefinitely
- founders see stale execution state with no useful intervention path
- retry and replay semantics become muddy because the failure never resolves

## Why This Matters

`RISK-0021` already covers local cancellation/provider orphan behavior. This
risk is the worker-side equivalent: a task can disappear or hang inside the
execution runtime even if the control plane remains alive.

## Suggested Mitigation

- attach a hard timeout to every isolated worker dispatch
- reclaim stuck workers with an explicit watchdog path
- synthesize a `TimeoutReceipt` or equivalent failure receipt when reclaiming
- surface reclaim outcomes in founder/operator progress views

## Capability Gate
- Capability: isolated worker proof (Step 12-b)
- Gate mode: Before Next Phase
- Blocked until: control plane can deterministically reclaim timed-out or
  crashed workers

## Issue Link
- GitHub Issue: #29

## Doc Links
- ADR:
- Design note: ../../issues/STEP_12B_ISOLATED_WORKER_PROOF.md

## Exit Criteria

- every isolated worker dispatch has a hard timeout
- timed-out or crashed workers produce a typed receipt
- replay and progress views can explain reclaim outcomes

## Last Updated
- 2026-04-17
