# Step 17 - Execution Leases And Orphan Reconciliation

## What changed

Step 17 adds a typed execution-claim layer for bounded worker dispatch.

Key additions:

- `ExecutionClaimRecord` in the ledger
- `ExecutionClaimView` / `ExecutionClaimRefusalView` domain models
- lease-aware guard on:
  - worker dispatch
  - approval resolution
  - founder reply / patch mutation lanes
- reclaim path for expired claims
- lease visibility in:
  - run snapshot
  - progress surface
  - CLI inspection

## Claim model

Each run now has at most one active execution claim at a time.

The claim records:

- `runtime`
- `owner`
- `lease_token`
- `acquired_at`
- `heartbeat_at`
- `expires_at`
- `released_at`
- `reclaim_reason`

## Dispatch guard

Before bounded execution starts, the store tries to acquire a claim.

If another live claim already exists:

- dispatch is refused with `ExecutionClaimConflictError`
- the refusal includes the existing claim payload
- CLI/status can show the active owner and expiry

## Reclaim policy

Step 17 uses pessimistic reclaim.

- lease TTL is derived from task timeout plus small slack
- once expiry is observed, the old claim is reclaimed
- reclaim records:
  - task failure when needed
  - claim reclaimed event
  - system audit observation

For containerized execution, reclaim attempts hard container kill before the
claim is reopened.

## Mutation guard

Approval-sensitive paths now check for active claims before mutating state.

That includes:

- approval resolution
- founder reply handling
- patch intake mutation lanes

This keeps execution ownership and governance mutation from silently
interleaving.

## CLI surface

Step 17 adds:

- `v2-spring task claim <run-id>`
- `v2-spring task reconcile-claims <run-id>`

These expose the current claim owner and allow explicit reclaim of expired
claims.

## Risk posture after Step 17

- current-scope lease-aware concurrency is now covered
- current-scope reclaim visibility is now covered
- remaining hardening risks are:
  - `RISK-0046`
  - `RISK-0047`
  - `RISK-0048`

## Feedback Incorporated

- Concurrency feedback pushed this slice to make execution ownership explicit
  instead of inferred from task status.
- Orphan-handling feedback also required reconcile and claim visibility to stay
  founder/operator visible rather than becoming silent background behavior.
- This step intentionally established the lease model first and deferred
  renewal, atomicity hardening, and fencing into Step 18.
