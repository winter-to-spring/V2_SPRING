# Step 4 Implementation Note: Approval Hardening

## What This Slice Adds

Step 4 hardens the first human-in-the-loop boundary without turning the tracer
bullet into a full operations platform.

This slice adds:

- structured rejection feedback for approval resolution
- a service-level write barrier while a run is waiting for approval
- a shared risk register so future work can inherit unresolved risks instead of
  depending on individual memory

## Why This Matters

The first approval loop proved that a human can stop or continue a run.

That was necessary, but not yet sufficient.

If rejection carries no explanation, the next planner loop is likely to repeat
the same mistake. If a run can keep mutating while an approval is pending, the
approval gate is performative rather than real.

This slice closes both gaps at the smallest useful level.

## What We Deliberately Leave For Later

- approval timeout / expires_at / suspended semantics
- watchdog-driven cleanup for abandoned approvals
- stronger DB-level or distributed locking for concurrent workers

Those are still important, but they belong to the next scaling and concurrency
phase rather than this tracer-bullet hardening step.
