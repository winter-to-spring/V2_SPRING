# ADR 0006: Bounded Replanning Loop and Planner Attempt Governance

## Context

Step 8 introduced a typed planner proposal contract and a legal-action guard,
but it intentionally stopped short of governing repeated planner failure.

Before attaching any real LangGraph adapter or automatic replanning loop, the
system must answer four questions deterministically:

1. How many planner mistakes are allowed inside one state segment?
2. Which failures should consume planner retry budget?
3. How are duplicate submissions handled?
4. How can a founder explicitly reopen an exhausted planner phase?

Without those answers, a future planner could loop forever on stale hashes,
illegal actions, or repeated proposals while burning tokens and cluttering the
ledger.

## Decision

V2_SPRING will use a **phase-scoped planner budget** plus an append-only
planner-attempt ledger.

- Planner retries are bounded per **phase**, not globally for the whole run.
- A phase is identified by a deterministic `planner_phase_key`.
- The phase key is derived from meaningful advancement signals only:
  - run status
  - pending approval state
  - latest rejection reason
  - task summary
  - latest task headline
  - latest artifact headline
- Planner-only traces must **not** advance the phase:
  - accepted planner decisions
  - planner escalation records
  - founder-help lane markers
  - founder hint / reject / override bookkeeping
  - manual recharge records
- Examples:
  - resolving approval or completing a bounded task may advance the phase
  - opening or clearing a founder escalation must not advance the phase by itself

## Attempt Budget Policy

- The initial planner phase budget is `3`.
- These outcomes consume budget:
  - `rejected_stale`
  - `rejected_illegal`
  - `rejected_duplicate_cognitive`
- These outcomes do **not** consume budget:
  - `accepted`
  - `rejected_duplicate_transport`
  - `manual_recharge`
  - execution-time failures outside the planner proposal path
- When the phase budget is exhausted, the system records a
  `phase_exhausted` planner attempt and blocks further planner proposals until
  a founder explicitly recharges the phase.

## Duplicate Policy

Planner duplication is handled in two layers.

### Transport-level duplicate

- Definition: the same `submission_key` is submitted again inside the current
  active planner phase.
- Result: explicit rejection with
  `rejected_duplicate_transport`.
- Budget effect: does not consume planner budget.

### Cognitive duplicate

- Definition:
  - the same proposal fingerprint is repeated inside the current active planner
    phase, or
  - the same normalized proposal intent signature is repeated for the same
    action inside the current active planner phase, or
  - a proposal is submitted after one proposal has already been accepted in the
    same active planner phase and state has not advanced.
- Result: explicit rejection with
  `rejected_duplicate_cognitive`.
- Budget effect: consumes planner budget.

## Resume Policy

- Reopening a planner phase is a founder-controlled action.
- `manual_recharge` is allowed only when the current active phase is exhausted.
- Recharge requires an explicit non-blank reason.
- The founder can inspect `planner recharge-check` before reopening the phase.
- Recharge guidance must surface the latest failure / rejection / founder-help
  context that still affects the current phase.
- Repeated recharge, deterministic runtime blockage, or still-active rejection
  context require explicit acknowledgement before the phase can be reopened.
- Recharge resets the active-budget window for the current phase but does not
  delete past attempts.
- Past attempts remain replayable and auditable.

## External Failure Accounting

Planner proposal governance is separate from executor/runtime failure.

- If a proposal is legal and accepted, planner budget stops being the relevant
  control.
- Later execution failures such as timeout, filesystem errors, permission
  problems, or provider outages do **not** consume planner proposal budget.
- Those failures must be tracked through task / observation / artifact state and
  can create a new planning phase later.
- Repeated **deterministic** execution failure is a special case:
  - it still does not consume planner proposal budget directly
  - but once the same deterministic execution blocker repeats without state
    advancement, the system must open a founder-help escalation lane before it
    accepts another planner proposal
  - this keeps the planner/executor boundary honest without blaming the planner
    for one-off runtime noise

## Structured Outcome Contract

Every planner attempt is persisted as an append-only ledger-backed record with:

- `phase_key`
- `policy_version`
- `snapshot_hash`
- `selected_action`
- `submission_key`
- `proposal_fingerprint`
- `outcome`
- `outcome_reason`
- `attempt_index`
- `budget_limit`
- `budget_used`
- `budget_remaining`

This keeps replay and future planner analytics grounded in typed evidence
instead of free-form logs.

## Alternatives Considered

### Global run budget

Rejected for Step 9 because long runs could die late due to a few stale or
illegal planner attempts that happened much earlier.

### Silent duplicate drops

Rejected because silent drops hide failure from both founders and future
planners. Duplicate handling must be explicit.

### Budget reset on any new decision

Rejected because planner-only decisions would let the planner refresh its own
budget without meaningful progress.

## Consequences

### Positive

- Planner failure is finite and auditable.
- Founder-controlled recharge is possible without deleting history.
- Duplicate submissions are separated from repeated reasoning failure.
- A real planner adapter can target a stable legal-action contract later.

### Negative

- Snapshot hashes change as planner governance state changes, which makes
  manual CLI proof more verbose.
- Exact semantic duplicate detection is still imperfect and remains a separate
  risk.
- Phase-reset abuse still requires future hardening.
