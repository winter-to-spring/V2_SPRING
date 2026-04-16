# Step 3 Implementation Note: Approval + approval list/resolve CLI

## What This Slice Adds

Step 3 makes the first human-in-the-loop control visible and actionable from the
CLI.

The system now exposes:

- a typed `Approval` state model
- append-only approval request and resolution events
- `approval list`
- `approval resolve --approve|--reject`

## Why This Matters

V2_SPRING is intentionally semi-automatic.

That means "approval" cannot stay as an abstract design promise. It must exist
as:

- durable state
- deterministic transitions
- replayable evidence
- human-visible CLI controls

## Current Step 3 Behavior

When a run is created, the system also seeds a pending approval that asks the
human to allow the tracer bullet to continue beyond intake.

When the approval is resolved:

- the approval state changes in the state table
- the run state changes deterministically
- an append-only ledger event records the transition

## What This Does Not Yet Solve

- approval UI
- budget and hiring approvals
- task execution after approval
- replay summaries
- planner-driven approval requests

Those belong to later slices.
