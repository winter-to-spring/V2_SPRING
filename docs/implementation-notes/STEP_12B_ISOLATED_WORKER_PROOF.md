# Step 12-b: Isolated Worker Proof

## What This Slice Adds

Step 12-b proves that the execution plane can hand work to a separate runtime
without letting that worker mutate the control plane directly.

This slice adds:

- a strengthened soft-isolation worker runtime based on `subprocess`
- task-local workspace copying with secret-file exclusion
- bounded environment allowlisting
- synchronous hard-timeout reclaim with typed receipts
- temp-file stdout/stderr capture with bounded tail reads
- unified patch plus JSON receipt artifacts
- `v2-spring task dispatch <run-id> --runtime isolated_worker`

## Key Runtime Rules

- the worker never edits the main workspace directly
- the worker only returns a patch artifact and a receipt artifact
- `.env` and similar secret files are not copied into worker scope
- the worker receives a minimal allowlisted environment
- timeout reclaim happens synchronously at the subprocess boundary
- stdout/stderr are redirected to task-local temp files rather than live pipes

## Why Soft Isolation First

The goal of Step 12-b is to prove the execution-plane contract:

- dispatch
- bounded runtime execution
- receipt capture
- replayable audit trail

It is not yet the final sandbox security story.

That is why this slice intentionally uses strengthened soft isolation rather
than full container isolation, and separately tracks `RISK-0027` for the
remaining OS/container boundary gap.

## Artifacts Produced

Successful isolated worker proof dispatch produces:

- one unified patch artifact
- one execution receipt artifact

Failed or timed-out dispatch still produces:

- one execution receipt artifact

This keeps failure states replayable and founder-visible instead of disappearing
as silent runtime crashes.

## Risks Touched In This Slice

- `RISK-0023`: resolved for the Step 12-b proof boundary
- `RISK-0024`: resolved through timeout reclaim and temp-file log capture
- `RISK-0027`: remains open before unrestricted bypass-style workers can scale
