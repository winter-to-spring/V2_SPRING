# V1 WORKFLOW

## Goal

V1 focuses on a single reliable workflow:

`Manager -> PM -> Builder -> QA`

The purpose of v1 is not full autonomy. The purpose is to prove that a
single request can move through a controlled workflow with visible state,
artifacts, and quality gates.

## Phases

1. `inbox`
   A new request is created and assigned a request ID.
2. `requirements_drafting`
   The PM agent prepares the first PRD draft.
3. `planning`
   The system prepares the implementation plan and roadmap output.
4. `implementation`
   The Builder agent makes the scoped change.
5. `module_verification`
   QA validates the scoped work.
6. `completed`
   The workflow reaches a terminal state for v1.

## V1 agent responsibilities

- `Manager`
  Routes the task, sets the current phase, and manages ownership.
- `PM`
  Creates the PRD draft and captures acceptance criteria.
- `Builder`
  Produces the implementation plan and code changes for the scoped task.
- `QA`
  Records the test report and quality status for the run.

## V1 gates

### Automatic

- PRD first draft
- roadmap draft
- code scaffold generation
- lint, typecheck, unit, and smoke execution

### Human review required

- final PRD approval
- security, auth, billing, and permissions changes
- destructive database changes
- production deployment

## Required artifacts

- `docs/PRD.md`
- `docs/ROADMAP.md`
- `docs/TEST_REPORT.md`

## Exit criteria for v1

A workflow run is considered successful when:

- the request has moved through all defined phases
- the required artifacts exist
- the quality fields are recorded
- the current owner and blocker fields are visible in state

