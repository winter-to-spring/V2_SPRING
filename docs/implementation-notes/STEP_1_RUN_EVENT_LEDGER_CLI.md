# Step 1 Implementation Note: Run + EventLedger + CLI tracer bullet

## What This Slice Delivers

This slice proves the first durable loop of V2_SPRING:

- a human can create a `Run`
- the `Run` is validated before persistence
- a `RUN_CREATED` event is written to the append-only ledger
- the same run can be shown back from the CLI

## Why We Chose This Shape

We deliberately do **not** start with full event sourcing.

For Step 1, the simpler and safer choice is:

- state tables for the current truth
- append-only event ledger for replay and audit

This hybrid gives us a durable tracer bullet without front-loading avoidable complexity.

## Guardrails Applied

- `RunCreateInput` uses Pydantic validation with `extra=\"forbid\"`
- `UrgencyLevel`, `RiskLevel`, and `RunStatus` are explicit enums
- `EventLedgerRecord` is protected against update/delete at the ORM layer
- CLI read and write paths go through the same typed store boundary

## What Comes Next

Once this slice is stable, the next expansions should be:

1. `Decision`
2. `Task`
3. `Artifact`
4. `Approval`
5. `run replay`
