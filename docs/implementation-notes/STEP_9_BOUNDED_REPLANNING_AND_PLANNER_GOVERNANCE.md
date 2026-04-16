# Step 9 Implementation Note

## Scope

Step 9 turns the Step 8 planner proposal contract into a bounded replanning
loop with explicit governance.

This slice adds:

- typed planner attempts
- phase-scoped attempt budgeting
- duplicate handling
- phase exhaustion
- founder-controlled manual recharge
- replay visibility for planner governance

It still does **not** attach a real LangGraph planner.

## Attempt Accounting Rules

- Planner attempts are append-only.
- Each attempt records:
  - phase key
  - snapshot hash
  - policy version
  - selected action
  - optional submission key
  - optional proposal fingerprint
  - structured outcome
  - budget counters
- The store is the only place allowed to write planner attempts.

## Budget Reset Rules

- Budget is phase-scoped.
- Phase advancement is derived from stateful progress signals, not planner-only
  decision records.
- Accepted planner proposals do not automatically reset the phase budget.
- Manual recharge reopens the active budget window for the current phase, but
  past attempts remain visible in replay.

## Resume Semantics

- Recharge is founder-controlled and explicit.
- Recharge is rejected unless the current active phase is exhausted.
- Recharge requires a non-blank human reason.
- Recharge now exposes a founder-facing preflight surface before scale:
  - `planner recharge-check <run-id>`
  - latest failure / rejection / founder-help context
  - explicit acknowledgement when the current blockage still looks unchanged
- Recharge records both a planner attempt and a system-audit observation.

## Duplicate Detection

### Transport duplicate

- Trigger: repeated `submission_key`
- Outcome: `rejected_duplicate_transport`
- Budget effect: none

### Cognitive duplicate

- Trigger:
  - same proposal fingerprint inside the current active phase, or
  - any new proposal after one accepted proposal already exists in the same
    active phase without state advancement
- Outcome: `rejected_duplicate_cognitive`
- Budget effect: consumes planner budget

## External Failure Handling

Planner governance only meters planner proposal failure.

- stale hash, illegal action, and cognitive duplicate consume planner budget
- accepted proposals do not
- transport duplicates do not
- executor/runtime failures after a legal proposal do not consume planner budget

Those later failures belong to task / artifact / observation handling and may
create a new replanning phase.

## Outcome Event Schema

Planner governance writes:

- one immutable `PlannerAttemptRecord`
- one append-only `PLANNER_ATTEMPT_RECORDED` ledger event
- optional `SYSTEM_AUDIT` observation when the founder or future debugging flow
  needs a human-readable explanation

The intended outcome vocabulary is:

- `accepted`
- `rejected_stale`
- `rejected_illegal`
- `rejected_duplicate_transport`
- `rejected_duplicate_cognitive`
- `phase_exhausted`
- `manual_recharge`

## CLI / Read Model Expectations

Step 9 extends the CLI with:

- `planner propose`
- `planner show`
- `planner attempts`
- `planner recharge`

Replay defaults to a summary of planner governance attempts and shows the full
attempt trail under `--verbose`.

## Tests Added

- budget exhaustion after three budget-consuming failures
- transport duplicate rejected without budget consumption
- manual recharge reopens the exhausted phase
- replay includes planner attempts

## Deferred Hardening

Still deferred after Step 9:

- semantic duplicate equivalence beyond exact fingerprints
- stronger TOCTOU protection under concurrency
- planner-facing payload hygiene and sanitization hardening
