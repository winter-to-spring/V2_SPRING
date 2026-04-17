# Step 7 Implementation Note: RunSnapshot + deterministic possible actions

## What This Slice Adds

Step 7 gives the system a planner-ready inspection surface before any LLM is
attached.

This slice adds:

- a bounded `RunSnapshot` typed model
- a deterministic `possible actions` engine
- CLI commands for `run snapshot` and `run actions`

## Why This Matters

Step 6 proved that the system can replay what already happened.

Step 7 proves something different:

- the system can summarize the current run state without bloating context
- the system can enumerate legal next moves without making planner judgments

That is the last missing deterministic layer before planner/replanner work can
begin.

## Snapshot Design

`RunSnapshot` is intentionally small.

It includes:

- run status and metadata
- pending approval, if any
- latest rejection reason, if any
- latest decision summary
- task status counts
- latest task headline
- latest artifact headline
- `snapshot_timestamp`
- `state_hash`

It does **not** include:

- raw ledger event dumps
- full artifact bodies
- filesystem paths for planner use
- stdout/stderr history beyond a compact failure hint

This keeps the snapshot founder-readable and planner-safe.

## Possible Actions Policy

The possible-actions engine is a **legal-moves generator**, not a planner.

It may:

- state what actions are legal right now
- explain why they are legal
- attach bounded context hints

It may not:

- rank actions probabilistically
- choose one action as "best"
- mutate state
- bypass approval boundaries

## Current Action Set

This slice intentionally starts with a fixed enum:

- `resolve_pending_approval`
- `execute_bounded_task`
- `replan_with_rejection_feedback`
- `replan_from_failed_execution`

Custom user-defined actions are explicitly deferred.

## Terminal And Stuck States

An empty action list is not enough on its own.

The snapshot also carries an `action_state`:

- `available`
- `blocked`
- `terminal`
- `stuck`

This prevents ambiguity between:

- "the run is done"
- "the run is temporarily blocked"
- "the run has entered an unexpected gap with no legal move"

## Deferred Risks

This slice intentionally does **not** fully solve:

- snapshot freshness under highly concurrent writers
- materialized replay/snapshot read models
- richer planner schemas
- custom action injection

Those risks remain documented in the shared risk register and should gate later
planner/scale work.

## Feedback Incorporated

- Later planner-facing feedback repeatedly asked for a legal-move surface that
  separates "blocked" from "terminal" from "unexpected gap".
- That validated the Step 7 action-state model and the decision to keep
  snapshots derived from authoritative state instead of materializing a second
  mutable projection.
- Snapshot freshness concerns raised here stayed open until the Step 20
  freshness-anchor hardening.
