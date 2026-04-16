# Architecture Overview

V2_SPRING is organized into four layers:

1. **Ledger and Governance**
   - durable entities
   - approvals
   - budgets
   - risks

2. **Deterministic Substrate**
   - Postgres
   - Redis
   - queue and lease semantics
   - deterministic executors

3. **Autonomous Cognition**
   - LangGraph planner and replanner
   - action proposal and selection

4. **Execution Workforce**
   - CrewAI specialist execution pools
   - builders
   - QA
   - integrators

Human verification sits above all four layers and must be supported by stored evidence.
