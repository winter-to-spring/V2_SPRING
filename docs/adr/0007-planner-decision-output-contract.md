# ADR 0007: Structured Planner Decision Output Contract

## Context

Step 10 is the first point where a real planner adapter enters the V2_SPRING
control plane.

By Step 9 we already had:

- typed run/task/approval/task-artifact state
- replayable planner attempts
- bounded planner phase budgets
- deterministic legal-action evaluation

The next risk was not only "can an LLM answer?" but "can an LLM answer without
either suffocating into V1-style rigidity or escaping the governance model?".

Two failures had to be avoided at the same time:

1. free-form text outputs that are hard to parse, govern, or audit
2. overly narrow schemas that force the planner to guess an action even when it
   should escalate

## Decision

Step 10 adopts a **structured, discriminated-union planner output contract**.

The planner adapter returns one of two legal proposal shapes:

- `ActionProposal`
- `EscalationProposal`

Both proposals are schema-validated and selected via the explicit `kind`
discriminator.

## Why Structured Outputs

V2_SPRING needs a planner slot that is:

- machine-readable
- replayable
- bounded by governance
- robust against parser drift

Free-form text makes parser loops and hidden planner drift too easy.

Therefore Step 10 keeps structured outputs as the default path.

## ActionProposal vs EscalationProposal

`ActionProposal` is for a normal next move that already exists inside the
deterministic legal-action engine.

`EscalationProposal` is for founder-facing governance requests when the planner
cannot safely choose a next action.

This separation preserves domain purity:

- the legal-action engine remains an execution-domain component
- escalation remains a governance-domain component

We do **not** encode escalation as a normal action enum.

## Reasoning Summary Policy

The planner must still be allowed to explain itself.

However, V2_SPRING does not store raw chain-of-thought.

Instead, the contract requires bounded reasoning metadata such as:

- `analysis_summary`
- `confidence`
- `blocking_reason`
- `requested_help`

This preserves observability without turning the ledger into a chain-of-thought
dump.

`confidence` is treated as an observational signal, not a safety authority.

## Hint-First / Override-Available Policy

Founder interaction follows this policy:

- default path: the founder gives a structured hint and the planner proposes
  again
- exception path: founder override remains available for future governance
  surfaces

This keeps planner autonomy meaningful without removing founder control.

Step 10 only formalizes the **hint-first** side of this policy; override
handling remains a follow-up capability.

## Failure Reporting Policy

Planner input does not receive raw ledger events.

Instead, Step 10 uses a bounded `StructuredFailureReport` that contains enough
signal for self-correction without exposing the full raw ledger.

At minimum the planner receives:

- failure class
- normalized error code
- short sanitized traceback
- normalized failure signature
- previous rationale
- observed outcome

This is intentionally a summarized report, not raw log replay.

## Consequences

Benefits:

- the planner can think inside a typed contract without being forced to fake an
  action
- governance remains explicit and replayable
- parser drift becomes observable and bounded
- action selection and escalation are no longer conflated

Costs:

- the summarizer now matters more; if it loses key failure details, planner
  quality drops
- founder reply semantics need their own contract later
- escalation can still thrash if not governed by future policies

## Follow-up

This ADR leaves follow-up work for later phases:

- founder reply contract for hint vs override
- escalation throttling / cooldown policy
- stronger failure-report fidelity checks
- production transport integration beyond scripted proof mode
