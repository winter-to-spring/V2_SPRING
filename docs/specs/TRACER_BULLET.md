# V2_SPRING Tracer Bullet

## Purpose

This tracer bullet is the first end-to-end proof that V2_SPRING can run a
bounded autonomous loop without a UI.

It is intentionally small.

We are not proving:
- multi-agent scale
- rich UI
- dynamic hiring
- broad workflow coverage

We are proving:
- state is durable
- decisions are recorded
- execution is bounded
- human approval works
- replay is possible

## Minimal Loop

### Step 1. Submit one request

A human starts a run from the CLI.

Example:

```bash
v2 run create \
  --project demo \
  --goal "Analyze the repository structure and propose a refactor plan" \
  --urgency normal \
  --risk medium
```

Expected result:
- a `Run` is created in Postgres
- an initial `Observation` is recorded
- an initial `Decision` record explains that the run entered planning
- the append-only ledger captures all three bootstrap events

### Step 2. Build a state snapshot

The system creates a normalized snapshot for planner input.

Expected result:
- a `RunSnapshot` artifact exists
- snapshot includes:
  - run metadata
  - current approvals
  - current risks
  - current tasks
  - relevant observations

### Step 3. Generate possible actions

The system computes allowed next actions before consulting the planner.

For the tracer bullet, possible actions are deliberately tiny:
- `plan_bounded_task`
- `request_human_approval`
- `cancel_run`

Expected result:
- a `Decision` or `Observation` record stores the candidate actions

### Step 4. Planner selects one action

The planner chooses one next action from the allowed set.

For this first loop, the happy path should be:
- choose `plan_bounded_task`

Expected result:
- planner output is stored as a `Decision`
- planner does not mutate state directly

### Step 5. Executor performs one bounded task

The executor creates exactly one task and performs exactly one safe action.

Recommended bounded task for the first loop:
- read a repository tree
- write a short analysis artifact

Expected result:
- a `Task` is created
- the `Task` transitions through deterministic states
- an `Artifact` is produced
- an `Observation` captures execution outcome

### Step 6. Request human approval

The system pauses for a mandatory approval before finalizing the run.

Example:

```bash
v2 approval list
v2 approval resolve <approval-id> --approve
```

Expected result:
- an `Approval` exists in Postgres
- CLI can show why approval is needed
- approval or rejection is recorded as a structured event

### Step 7. Finalize or replan

If approved:
- run completes
- final result package is written

If rejected:
- run records rejection
- planner may re-enter with a bounded replan path

Expected result:
- final `Run` state is deterministic
- run end condition is explicit

### Step 8. Replay from ledger

A human can reconstruct what happened without trusting memory.

Example:

```bash
v2 run show <run-id>
v2 run events <run-id>
v2 run replay <run-id>
```

Expected result:
- input is visible
- decisions are visible
- task lifecycle is visible
- approval lifecycle is visible
- artifacts are visible

## Required Domain Objects

The tracer bullet only needs a minimal subset:
- `Project`
- `Run`
- `Task`
- `Decision`
- `Artifact`
- `Approval`
- `Observation`

It does not need full module graphs or dynamic hiring yet.

## Required Invariants

1. Planner never changes persistent state directly.
2. Executor only executes allowed actions.
3. Every state change produces a durable ledger event.
4. Every run is replayable from stored records.
5. Approval is required before final completion.
6. Failure is recorded explicitly, not silently skipped.

## CLI Surfaces Required

Minimum commands:
- `v2 run create`
- `v2 run show`
- `v2 run events`
- `v2 approval list`
- `v2 approval resolve`
- `v2 run replay`

Optional but helpful:
- `v2 task list`
- `v2 artifact list`

## Acceptance Criteria

The tracer bullet passes only if all of these are true:

1. A human can create a run from the CLI.
2. A planner decision is stored in Postgres.
3. A bounded task executes and produces an artifact.
4. Human approval is required and resolvable from the CLI.
5. The run can be replayed from the ledger after completion.
6. No UI is required to confirm correctness.

## What This Buys Us

If this tracer bullet works, then we have proved:
- the substrate is real
- the planner/executor split is real
- approvals are not hand-wavy
- verification is possible without a custom frontend

Only after this passes should we add:
- richer planner loops
- CrewAI execution pools
- founder UI
- operator UI
- autonomous hiring
