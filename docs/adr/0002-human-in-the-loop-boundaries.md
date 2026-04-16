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
