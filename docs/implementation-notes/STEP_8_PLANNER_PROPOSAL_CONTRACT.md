# Step 8 Implementation Note: Planner proposal contract + legality guard

## What This Slice Adds

Step 8 adds the first real planner-facing contract without attaching a real LLM.

This slice introduces:

- a typed `PlannerProposal` input contract
- deterministic legality validation against the current legal move set
- snapshot-hash freshness checks
- policy-version visibility folded into the snapshot hash contract
- CLI proof commands for `planner propose` and `planner show`

## Why This Matters

Step 7 proved that the system can expose a planner-ready snapshot and legal
actions.

Step 8 proves the next layer:

- a planner can only propose from that legal move set
- the proposal must match the exact snapshot the planner saw
- accepted proposals are durable and replayable as decisions

This gives LangGraph a safe slot later, instead of asking it to speak directly
to the executor or the database.

## Contract Policy

`PlannerProposal` stays intentionally small:

- `snapshot_hash`
- `selected_action`
- `rationale`
- `expected_outcome`

No ranking, no probabilities, no custom free-form action names.

That keeps the contract auditable and deterministic.

## Legal-Move Validation

The proposal path does **not** reimplement action legality in parallel.

Instead, it calls the same `evaluate_possible_actions()` function that powers
`run actions`.

That matters because legality drift would otherwise create a split brain:

- the founder sees one set of legal moves
- the planner validator enforces another

Step 8 avoids that by using one deterministic source.

The same engine now also carries an explicit policy version. That version is
surfaced in snapshots and folded into the `state_hash`, so a future engine
policy change naturally invalidates old proposals instead of silently
pretending cross-version compatibility exists.

## Freshness Policy

The proposal must carry the `snapshot_hash` it was created against.

If the current hash no longer matches, the proposal is rejected as stale.

This is intentionally strict at current CLI scale. We prefer obvious failure
over quietly accepting a proposal built against an old world-model.

Rejected proposals are not silently dropped.

Step 8 records a `SYSTEM_AUDIT` observation whenever a proposal is rejected for
staleness or illegality. Rejected illegality checks also include the current
action state and legal action reasons, so the planner boundary is easier to
debug when a proposal is blocked. This keeps replay and debugging honest even
though no planner `Decision` is written for rejected proposals.

## Approval Boundary Policy

Planner proposals are allowed to be recorded while a run is waiting on human
approval **only when they are non-mutating evidence**.

That means:

- the system may record that the planner proposes `resolve_pending_approval`
- the system may **not** treat that proposal as execution
- run state does not advance until the human actually resolves the gate

## Deferred Risks

This slice still defers:

- stronger snapshot freshness guarantees under concurrent writers
- custom user-defined action systems
- richer planner adapters and automatic chaining

Those remain capability-gated and should not be confused with what Step 8
actually proves.

## Feedback Incorporated

- Later governance feedback favored typed planner proposals and explicit audit
  on refusal rather than ad-hoc planner output handling.
- Review pressure also pushed this slice to keep approval-waiting proposals
  evidence-only so the planner could not mutate through a human gate.
- This contract became the stable seam for later transport, founder reply, and
  bounded replanning work.
