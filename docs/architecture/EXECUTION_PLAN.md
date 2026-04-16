# V2_SPRING Execution Plan

## Intent

V2_SPRING is a clean-room rebuild of the autonomous software studio.

We are not carrying V1 forward as the product core. We will only reuse proven
ideas, documents, and infrastructure direction from earlier work.

## Phase 1. Charter And Boundaries

Goal:
- lock the system charter before implementation expands again

Deliverables:
- system purpose and non-goals
- human-in-the-loop boundaries
- success criteria for "autonomous but governable"
- initial ADR set

Questions this phase must answer:
- what is the product actually for
- what decisions remain human-approved
- what must never depend on agent memory

## Phase 2. Core State Model

Goal:
- define the stable domain model before building orchestration

Core entities:
- Project
- Run
- Module
- Task
- Capability
- Decision
- Artifact
- Approval
- Budget
- Risk
- Observation

Deliverables:
- domain model
- lifecycle definitions
- invariants
- event ledger design

Questions this phase must answer:
- what is the source of truth
- what can change when agents scale
- what must remain invariant even if many agents are added

## Phase 3. Deterministic Substrate

Goal:
- build the reliable system of record first

Scope:
- Postgres for record
- Redis for coordination
- queue and lease semantics
- approvals and budget policies
- cancellation, retry, and resume semantics

Deliverables:
- app skeleton
- infra bootstrap
- deterministic executor contracts
- event storage and replay foundation

Questions this phase must answer:
- how state is persisted
- how concurrent execution is kept safe
- how a run ends, pauses, resumes, or is cancelled

## Phase 4. Planner And Replanner Layer

Goal:
- move from hardcoded routing to action selection

Scope:
- state snapshot
- possible actions
- policy guard
- planner output schema
- replanning loop

Primary target:
- LangGraph as planner and replanner

Questions this phase must answer:
- how next actions are generated
- how risk and approval affect planning
- how the system re-enters a run after blockers or feedback

## Phase 5. Execution Workforce

Goal:
- attach specialist execution crews without changing the substrate

Scope:
- capability registry
- execution pools
- module builders
- QA and integration workers

Primary target:
- CrewAI as execution workforce

Questions this phase must answer:
- who is fit for a task
- how additional agents affect capacity rather than topology
- how execution feedback returns to the planner

## Phase 6. Founder Verification Surface

Goal:
- make the full process inspectable by a human without reading raw logs

Scope:
- request input
- live process trail
- approval interactions
- artifact and result storage
- run history and replay

Questions this phase must answer:
- what was requested
- how it was handled
- who worked on it
- what documents and artifacts were produced
- what risks remain

## Phase 7. Autonomy Expansion

Goal:
- expand bounded autonomy without losing control

Scope:
- hiring proposal flow
- budget review flow
- observer roles
- external health monitoring
- self-improvement loops

Questions this phase must answer:
- what the system may decide by itself
- when it must escalate
- how to improve itself without drifting from founder intent

## Immediate Priority

We should start with:
1. Phase 1 charter
2. Phase 2 state model
3. Phase 3 deterministic substrate

The planner, crews, and UI should sit on top of those three foundations.
