# Step 22 - Postgres Contention And Controller DB Boundary

## What changed

- extended `v2-spring doctor` from schema-only output into a richer database
  doctor report with:
  - controller-mediated DB boundary visibility
  - blocked worker DB env vars
  - PostgreSQL pool diagnostics
  - PostgreSQL lock / activity diagnostics
- added a live PostgreSQL contention smoke probe that:
  - creates a temporary run / task / claim fixture
  - holds the claim hot path under row lock
  - measures whether a contender blocks behind that lock
  - samples lock waiting and pool utilization while the wait is happening
- hardened execution-claim mutation order so the hot paths acquire locks in a
  more consistent order:
  - run row first
  - claim row second
- moved reclaim cleanup onto raw SQL cascade cleanup for the smoke harness so
  append-only ledger protections stay intact for normal ORM usage

## Controller DB boundary

Step 22 keeps the controller as the only intended DB writer surface.

Workers still do not receive `DATABASE_URL`, `REDIS_URL`, or Postgres-specific
credentials through their allowlisted execution environments. The doctor surface
now makes that boundary explicit instead of leaving it implicit in runtime code.

## Contention visibility

The new doctor report exposes the first operational signals we agreed to care
about in this phase:

1. lock waiting
2. connection utilization
3. transaction latency

The PostgreSQL doctor path now surfaces:

- total / active connections
- lock-waiting connections
- idle-in-transaction connections
- longest live transaction age
- pool size / checked-out / overflow / utilization

## Smoke harness scope

The Step 22 smoke harness is intentionally narrow.

It is not a full load test. It is a proof that:

- row locks are actually being contended
- the contender blocks instead of racing through incorrectly
- operator surfaces can see the contention while it is happening

This gives us a reliable signal for `RISK-0058` and better operational
observability for `RISK-0055`, `RISK-0057`, and `RISK-0061`.

## What is intentionally not done yet

- no JSONB table split or lean heartbeat table yet
- no WAL / archival tuning yet
- no cache layer in front of the controller
- no external side-effect fencing expansion

## Verification

- `tests/test_step22_postgres_contention.py`
- `tests/test_step21_postgres_migration.py`
- `python3 -m compileall src`
- disposable live PostgreSQL smoke through Docker

## Risk impact

- `RISK-0058` is resolved for the current Postgres hot path because lock order
  is now explicit and live contention smoke passes
- `RISK-0055` remains mitigating, but the controller boundary and pool
  diagnostics are now operator-visible
- `RISK-0057` remains mitigating, but contention behavior is now measured
  instead of assumed
- `RISK-0061` moves to mitigating through explicit controller-boundary
  diagnostics rather than remaining opaque

## Feedback Incorporated

- Contention feedback pushed this slice to move from "Postgres boots" to "we
  can observe who is blocking whom under load".
- That directly led to lock-wait diagnostics, controller-boundary visibility,
  and live contention smoke against disposable Postgres.
- Deadlock feedback also forced a more explicit lock acquisition order in the
  claim hot path instead of relying on incidental ORM ordering.
