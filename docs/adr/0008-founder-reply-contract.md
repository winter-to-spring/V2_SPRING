# ADR 0008: Founder Reply Contract

## Status

Accepted

## Context

Step 10-a introduced `EscalationProposal` as a bounded planner output.

That created a new gap:

- the founder could receive a planner escalation
- but the founder response itself was not yet typed
- and the system had no deterministic answer for what hint, override, or reject
  should do next

Without a founder reply contract, the human-in-the-loop lane would drift back
into free-form chat semantics and replay would lose meaning.

## Decision

We standardize founder replies as a discriminated union with three bounded
response kinds:

1. `hint`
2. `override`
3. `reject`

Additional rules:

- founder replies bind to the **target escalation observation id**, not the
  current snapshot hash
- `override` is a **bounded override** and may only select an action that is
  currently present in the legal-actions set
- `reject` does not force the planner to guess again; it closes the current
  founder-help lane and exhausts the current planner phase
- `hint` does **not** auto-approve the next planner proposal; the planner must
  still re-enter the normal legality and governance path
- founder hint ping-pong is bounded with a **phase-scoped quota**; the current
  policy allows at most two founder hints before the next escalation attempt
  exhausts the current phase
- founder interventions are stored as replayable founder-specific records and
  summarized back into the next planner context window

## Consequences

### Positive

- founder interventions are explicit, replayable, and machine-readable
- planner/founder handoff no longer relies on ambiguous free text alone
- bounded override preserves legality guarantees without opening god mode
- reject semantics prevent the planner from hallucinating a random action after
  a failed founder-help request

### Negative

- the CLI surface becomes more structured and slightly heavier to use
- founder intervention policy must stay in sync with planner governance policy
- richer founder surfaces will still be needed later to reduce CLI typing
  friction

## Follow-up

- Step 10-b implements the founder reply contract and proof CLI
- Step 10-c will harden production transport, prompt policy, and richer founder
  feedback handling
