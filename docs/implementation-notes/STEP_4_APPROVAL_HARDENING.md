# Step 4 Implementation Note: Approval Hardening

## What This Slice Adds

Step 4 hardens the first human-in-the-loop boundary without turning the tracer
bullet into a full operations platform.

This slice adds:

- structured rejection feedback for approval resolution
- a service-level write barrier while a run is waiting for approval
- a shared risk register so future work can inherit unresolved risks instead of
  depending on individual memory
- explicit failure semantics when a blocked write crosses an approval barrier
- a narrow exception for passive audit observations that preserve visibility
  without reopening execution

## Why This Matters

The first approval loop proved that a human can stop or continue a run.

That was necessary, but not yet sufficient.

If rejection carries no explanation, the next planner loop is likely to repeat
the same mistake. If a run can keep mutating while an approval is pending, the
approval gate is performative rather than real.

This slice closes both gaps at the smallest useful level.

## Error Policy

When a write is blocked by a pending approval, the system must fail
explicitly.

That means:

- no silent drop
- no best-effort mutation
- no pretending the write succeeded

Today the CLI surfaces this as a non-zero exit with a clear error message.

When an HTTP surface is introduced, this same domain rule should map to an
explicit API error such as `423 Locked` or `409 Conflict`, together with a
machine-readable error code.

## Observation Boundary

Not every write during `waiting_approval` should be treated the same.

Two classes now exist:

- **stateful or planner-driving writes**
  - decisions
  - follow-up observations
  - anything that implies the run progressed
- **passive audit observations**
  - operational notes
  - external checks
  - error visibility that does not move the run forward

The approval barrier still blocks the first class.

The second class is allowed so the system does not become blind while a human
is deciding.

## Approval Timeout Closure

Approval wait is no longer an unbounded pause.

The current tracer bullet now adds:

- `expires_at` on every approval record
- an explicit `expired` approval outcome
- a deterministic `suspended` run state when an overdue approval is swept
- `v2-spring approval sweep-timeouts` as the current founder/operator-facing
  timeout mechanism
- replay and approval list visibility for expiry state and timeout reason

This keeps the current CLI flow deterministic without pretending we already
have a background watchdog. A future worker can call the same sweep logic on a
schedule, but the domain rule now already exists.

## What We Deliberately Leave For Later

- watchdog-driven cleanup for abandoned approvals
- stronger DB-level or distributed locking for concurrent workers

Those are still important, but they belong to the next scaling and concurrency
phase rather than this tracer-bullet hardening step.
