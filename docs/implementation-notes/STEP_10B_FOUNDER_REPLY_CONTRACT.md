# Step 10-b: Founder Reply Contract

## What This Slice Adds

Step 10-b closes the founder side of the planner escalation loop.

The system now supports three typed founder reply paths:

- `hint`
- `override`
- `reject`

Each reply is recorded as a replayable founder intervention tied to a specific
planner escalation observation.

## Key Runtime Rules

- planner escalation opens a founder-help lane and blocks new planner proposals
- founder replies target the **open escalation id**, not the current snapshot
  hash
- founder `hint` clears the pending escalation and allows the planner to try
  again under the normal legality/governance checks
- founder `override` may only select an action that is currently legal
- founder `reject` closes the founder-help lane and exhausts the current
  planner phase
- founder hints do not auto-approve the next planner action
- repeated founder hints are bounded per phase

## Why The Phase Key Changed

The founder-help lane itself must not reset planner retry budget.

To preserve the bounded replanning contract, `planner_phase_key` excludes
planner-only and founder-only bookkeeping such as:

- open founder escalation markers
- latest founder intervention summary

Those details still belong in the snapshot hash and planner context, but they do
not count as meaningful advancement.

Regression coverage now proves both sides of the rule:

- meaningful progress such as approval resolution or bounded task completion
  changes `planner_phase_key`
- founder escalation bookkeeping, founder hints, and repeated deterministic
  failure escalations do not

## Replay / CLI Surface

The CLI now exposes:

- founder interventions list
- founder reply commands for `hint`, `override`, and `reject`
- replay output that shows founder interventions in both summary and verbose
  views

## Risks Touched In This Slice

- `RISK-0010`: phase budget reset abuse
- `RISK-0016`: premature escalation thrash
- `RISK-0017`: founder reply contract ambiguity
- `RISK-0018`: founder reply CLI ergonomics

`RISK-0017` is resolved in this slice.

`RISK-0016` is resolved in the current founder-help loop.

`RISK-0010` is resolved for the current bounded planner lane and should only be
reopened if future planner-visible state introduces new advancement signals.

`RISK-0018` remains open and is intentionally deferred until a richer founder
surface exists.

## Feedback Incorporated

- Feedback on founder intervention ambiguity pushed this slice to make `hint`,
  `override`, and `reject` separate, typed paths.
- That same pressure exposed CLI ergonomics limits for multiline input, which
  stayed intentionally open until the richer founder/operator surface.
- The result was a narrower but much more replayable founder-help loop.
