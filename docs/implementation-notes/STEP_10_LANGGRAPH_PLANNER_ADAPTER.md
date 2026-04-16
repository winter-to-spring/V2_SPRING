# Step 10: LangGraph Planner Adapter

## Scope

Step 10 adds the first bounded LangGraph planner adapter path on top of the
Step 8/9 legality and governance substrate.

The goal is not full autonomy yet.

The goal is to prove that a planner can:

- read a bounded context window
- emit a structured proposal
- pass through the same legal guard as founder-entered proposals
- escalate explicitly when it cannot safely choose

## Decision Output Schema

The adapter returns a discriminated union:

- `ActionProposal`
- `EscalationProposal`

Both variants require:

- `analysis_summary`
- `confidence`

This preserves bounded reasoning metadata while keeping the output machine
readable.

## ActionProposal

`ActionProposal` maps directly into the existing Step 8 planner legality path.

The adapter converts it into the existing typed planner proposal input and
passes it through the deterministic legal guard.

## EscalationProposal

`EscalationProposal` does not masquerade as a legal action.

Instead, it records:

- one accepted planner attempt
- one planner-escalation observation

This keeps governance separate from action execution.

## Structured Failure Report

The adapter does not receive raw ledger events.

It receives a compact failure report built from the latest failed execution
evidence:

- `failure_class`
- `error_code`
- `short_traceback`
- `normalized_failure_signature`
- `previous_rationale`
- `previous_expected_outcome`
- `observed_outcome`
- `repeated_failure_streak`

The failure report now stays anchored to the planner proposal that actually
preceded the failed task. Later replanning proposals do not overwrite that
causal context.

When the same deterministic execution blocker repeats without state
advancement, the control plane does not keep looping silently.

Instead it opens a founder-help escalation lane before another planner proposal
is accepted, so the planner must either receive human guidance or stay blocked.

## Stale Fairness

Step 10 removes stale proposals from the main phase budget.

Instead:

- stale attempts now consume a separate stale quota
- stale quota is visible in snapshot/context
- once stale quota is exhausted, further stale attempts are rejected explicitly

This keeps stale timing churn from unfairly exhausting the main planner budget.

## Parse Failure Handling

The adapter uses schema-driven output validation and a bounded parse retry.

If the response still fails validation:

- the adapter records a `rejected_format` planner attempt
- a system-audit observation is written
- the failure is surfaced explicitly to the caller

## Hint-First Behavior

Step 10 prepares the system for hint-first founder intervention by allowing the
planner to escalate in a typed way.

Founder override is not implemented in this step.

That remains a later governance surface.

## Tests

Step 10 adds proof coverage for:

- stale quota fairness
- structured failure report generation
- planner invoke action path
- planner invoke escalation path
- planner invoke malformed response handling

## CLI / Replay Expectations

New CLI proof surface:

- `v2-spring planner invoke <run-id> ...`

This command shows:

- the bounded context window
- any current masking
- the parsed planner output
- the recorded decision id or escalation observation id
