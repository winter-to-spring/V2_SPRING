# Step 6 Implementation Note: Run replay summary + linkage queries

## What This Slice Adds

Step 6 turns the tracer bullet from a collection of separate CLI commands into
a readable execution narrative.

This slice adds:

- `run replay` as a replay/read-model surface
- `task show` for task-to-decision-to-artifact linkage
- `artifact show` for provenance and integrity checks
- pretty and JSON output formats for replay and detail queries

## Why This Matters

By the end of Step 5, V2_SPRING could prove that one bounded task executed and
left a durable artifact.

That still required the founder to assemble the story manually from:

- `run show`
- `run events`
- `task list`
- `artifact list`

Step 6 closes that gap by letting the system explain its own execution trail in
one place.

## Output Policy

The replay surface now has two output modes:

- `pretty`
  - optimized for human reading
  - summary first
  - success path first
- `json`
  - optimized for scripts, automation, and future UI adapters
  - contains the same core information in structured form

This keeps founder verification readable without sacrificing machine
consumability.

## Failed Attempt Policy

Failed attempts are not hidden or deleted.

However, the default pretty replay does not dump every failed branch in full.

Instead it:

- shows the main execution path first
- adds a dedicated failed-attempts section when failures exist
- keeps full detail available through JSON or command-specific detail views

This avoids turning replay into a wall of logs while still preserving evidence.

## Query Strategy

Replay is implemented as a fixed-query read model rather than a chain of
per-item lookups.

That means:

- runs, approvals, decisions, tasks, observations, and artifacts are fetched in
  batches
- linkage is assembled in memory
- ordering is stabilized with `timestamp + id` tiebreakers

This is enough for the current CLI scale and avoids early N+1 query drift.

## Integrity Behavior

`artifact show` and `run replay` both verify whether a filesystem-backed
artifact still exists and whether its current contents still match the stored
`sha256`.

This makes replay more trustworthy:

- missing artifact files are visible
- tampered artifacts are visible
- replay is not forced to pretend that pointers are always valid

Replay also raises consistency warnings when the durable state and recorded
ledger trail disagree in obvious ways, such as:

- a completed task without `TASK_COMPLETED`
- a failed task without `TASK_FAILED`
- an artifact present in state without `ARTIFACT_RECORDED`

## What This Still Does Not Solve

- event-sequence numbers for highly concurrent workers
- streaming replay for very large runs
- query projections stored as separate materialized views
- artifact version history for retries
- planner-driven branch visualizations

Those belong to later scaling and multi-agent slices.
