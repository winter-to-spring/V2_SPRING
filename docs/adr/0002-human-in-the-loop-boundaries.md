# ADR-0002: Human-In-The-Loop Boundaries

## Status
Accepted

## Context
Autonomy without governance leads to unsafe hiring, cost growth, and dangerous
changes being executed without review.

## Decision
Human approval is mandatory for:
- agent hiring
- budget increases
- destructive changes
- scope expansion
- any governance-tagged high-risk action

## Consequences
- Approval is a first-class domain entity.
- Planner outputs must support escalation and pause states.
- Full autonomy is intentionally not the first operating mode.
- The tracer bullet must expose approval creation and approval resolution
  through the CLI before any rich UI is attempted.
- Approval rejection must support structured feedback so replanning can learn
  from human guidance instead of repeating the same proposal.
- Approval-gated runs must reject non-approval writes until the gate is
  resolved, even before stronger concurrency controls are added.
- Approval barriers must fail explicitly. Silent drop is forbidden because the
  caller must know the write was blocked by governance rather than accepted.
- Approval gates are bounded pauses rather than infinite pauses. Each approval
  records `expires_at`, and an explicit timeout sweep may resolve overdue gates
  as `expired`, moving the run into `suspended` until a later recovery policy
  is introduced.
- Passive audit observations may still be recorded while approval is pending,
  but they must never advance state or act as planner-driving follow-up work.
