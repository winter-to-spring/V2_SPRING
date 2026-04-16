# Step 5 Implementation Note: Task + Artifact + bounded executor CLI

## What This Slice Adds

Step 5 is the first point where the tracer bullet leaves pure state changes and
produces a physical result on disk.

This slice adds:

- a typed `Task` model with deterministic lifecycle states
- a typed `Artifact` model with provenance metadata
- a bounded, read-only repository scan executor
- CLI surfaces for `run execute`, `task list`, and `artifact list`
- append-only ledger events for task and artifact flow

## Why This Matters

Until now, V2_SPRING could prove that a run was created, reviewed, and approved.

That was necessary, but still abstract.

Step 5 proves something more tangible:

- a human can approve a run
- the system can perform one bounded task
- the result is written to the filesystem
- the filesystem result is represented in typed state
- the ledger can explain how that result came to exist

## Safety Boundary

The Step 5 executor is intentionally narrow.

It does **not** edit code.

It only:

- scans one allowed workspace directory
- skips hidden and sensitive paths such as `.git` and `.env*`
- writes one text artifact under an explicit artifact root
- records enough provenance to verify the output later

This keeps the first execution slice small enough to trust.

## Provenance Rules

Every artifact now carries:

- `run_id`
- `task_id`
- optional `decision_id`
- `execution_context_id`
- `storage_kind`
- `command`
- `cwd`
- `size_bytes`
- `sha256`

This is the minimum metadata needed to make later replay and tamper checking
credible rather than aspirational.

## Execution Failure Behavior

The bounded executor can fail or time out.

When that happens:

- the task moves to `failed`
- the run moves to `failed`
- a `TASK_FAILED` ledger event is recorded
- an execution observation is recorded
- no artifact is persisted as a successful result

This keeps "work happened but the system cannot explain it" from becoming the
default failure mode.

## Atomicity Boundary

Step 5 still uses a hybrid model:

- state tables stay authoritative for the current projection
- the event ledger stays append-only

Filesystem output is written first, then persisted to state and ledger inside a
single database transaction.

If the DB write fails after the file is written, the file is deleted so we do
not leave behind an orphaned result that the ledger cannot explain.

## What This Still Does Not Solve

- distributed locking or multi-worker coordination
- artifact versioning for retries
- long-running executor watchdogs
- replay summaries that walk the full task/artifact graph
- planner-selected multi-task execution

Those belong to later execution and scaling slices.
