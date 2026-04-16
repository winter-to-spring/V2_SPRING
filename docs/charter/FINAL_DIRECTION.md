# V2_SPRING Final Direction

## Final Direction

V2_SPRING will not be a patched continuation of the Paperclip-based V1 system.

It will be a clean-room rebuild with this architecture:

- **Our control plane** as the system of record
- **LangGraph** as the planner and replanner layer
- **CrewAI** as the execution workforce layer
- **Human-in-the-loop governance** for hiring, budget, destructive change, and scope expansion
- **Founder verification surfaces** built on top of the ledger, not in place of it

The first milestone is not a full product.
The first milestone is a **CLI-verifiable tracer bullet**.

## What We Are Building

We are building a founder-controlled autonomous software studio.

This means:
- a human provides goals
- the system plans and replans
- execution workers perform bounded work
- important decisions are recorded
- risky actions require approval
- outcomes are inspectable and replayable

## What We Are Not Building

We are not building:
- a linear workflow engine
- a UI-first demo shell
- a prompt pile that pretends to be orchestration
- a system where agent memory is the source of truth
- a system where planner logic and state mutation are mixed together

## Adopted Principles

### 1. Ledger First

The source of truth is persistent structured state:
- Run
- Task
- Decision
- Artifact
- Approval
- Risk
- Budget
- Observation

Natural language summaries are not the source of truth.

### 2. Planner / Executor Separation

The planner may:
- inspect state
- propose next actions
- rank alternatives
- request approval

The planner may not:
- mutate persistent state directly

Only deterministic executors may mutate state.

### 3. Human Approval Is Core, Not Optional

Approval is mandatory for:
- hiring new agents
- budget increases
- destructive changes
- scope expansion
- other governance-defined high-risk actions

### 4. Replayability Is Required

Every run must be replayable from stored records.
A human must be able to reconstruct:
- what was requested
- what was decided
- what was executed
- what was approved
- what artifacts were produced
- why the run ended

### 5. Verification Before Surface Polish

The system must be provably correct from CLI and database evidence before
founder-facing UI becomes a primary effort.

## Main Risks We Accept And Mitigate

### Risk 1. State Desync

Mitigation:
- deterministic state transitions
- planner cannot mutate state
- execution receipts recorded as artifacts and observations
- replay checks

### Risk 2. Token Bankruptcy

Mitigation:
- full ledger is stored, but planner reads only snapshots and summaries
- memory management is explicit
- planner context is bounded

### Risk 3. LangGraph / CrewAI Impedance Mismatch

Mitigation:
- they do not integrate directly with each other
- they both integrate through our contracts
- our control plane remains the center

### Risk 4. UI Over-Engineering

Mitigation:
- no UI-first milestone
- first milestone is CLI-verifiable
- founder UI comes after tracer bullet proof

## Technology Direction

### System of Record
- Postgres for durable records
- Redis for coordination, queueing, lease, and wake-up semantics

### Cognition Layer
- LangGraph for:
  - planning
  - replanning
  - selecting possible actions
  - resuming after rejection or blockage

### Execution Layer
- CrewAI for:
  - bounded specialist work
  - builder crews
  - QA crews
  - reviewer and integration crews

### Verification Layer
- CLI first
- replay and event inspection
- founder surface later

## Immediate Build Order

1. Charter and boundaries
2. Core state model
3. Deterministic substrate
4. CLI tracer bullet
5. Planner contract
6. Executor contract
7. LangGraph integration
8. CrewAI integration
9. Founder verification UI

## Final Commitment

V2_SPRING is officially a:

**state-driven, ledger-backed, planner/executor-separated, human-governed autonomous software studio**

The first proof of success is not a polished UI.
The first proof of success is a run that can be:
- created from the CLI
- planned
- executed by one bounded worker
- approved by a human
- replayed from the ledger
