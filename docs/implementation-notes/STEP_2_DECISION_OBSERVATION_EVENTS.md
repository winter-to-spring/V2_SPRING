# Step 2 Implementation Note: Decision + Observation + run events

## What This Slice Adds

Step 1 proved that a typed `Run` can be created and shown.

Step 2 makes the first human-readable process trace visible from the CLI by
adding:

- append-only `Decision` records
- append-only `Observation` records
- `v2-spring run events <run-id>`

## Why This Matters

V2 cannot stop at "a run exists".

A founder or operator must also be able to inspect:

- what the system noticed
- what the system decided
- what immutable events were recorded in response

This is the first small proof of process visibility without building a UI.

## Current Step 2 Behavior

When a run is created, the system now also writes:

- one initial `Observation`
- one initial `Decision`
- matching append-only ledger events

The `run events` command reconstructs a readable timeline directly from durable
records.

## What This Does Not Yet Solve

- bounded task execution
- approval gates
- replay summaries
- artifact registry
- planner-produced decisions

Those belong to later slices.
