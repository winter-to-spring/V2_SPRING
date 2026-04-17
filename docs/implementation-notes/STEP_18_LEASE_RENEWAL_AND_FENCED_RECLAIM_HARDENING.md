# Step 18 - Lease Renewal And Fenced Reclaim Hardening

## What changed

Step 18 turns the Step 17 claim model into a stricter ownership contract.

Key additions:

- claim renewal / heartbeat path
- thresholded renew policy
- fencing token visibility in founder/operator surfaces
- version-gated atomic claim update on reacquire paths
- stale-result rejection when claim token/fencing token no longer match
- typed ledger/audit events for:
  - claim renewed
  - execution result rejected

## Renewal model

Workers do not decide expiry themselves.

They only request renewal with:

- execution context id
- lease token
- fencing token

The store checks the active claim and only extends it when the remaining TTL is
below a bounded renew threshold.

This avoids heartbeat spam while still keeping bounded long-running work alive.

## Fencing model

Each claim now exposes a `fencing_token` derived from the claim version.

That token is used in three places:

- founder/operator visibility
- renewal requests
- result acceptance

If the active claim version no longer matches the task/runtime result, the
result is rejected as stale.

## Atomicity hardening

Insert path:

- still one claim row per run
- concurrent insert conflicts degrade into typed refusal

Existing-row reacquire path:

- Step 18 upgrades this to a version-gated compare-and-swap update
- if the expected version no longer matches, the reacquire fails instead of
  silently overwriting ownership

## Stale-result handling

Late results from reclaimed or superseded workers no longer mutate task state.

Instead the store:

- records a typed `EXECUTION_RESULT_REJECTED` event
- stores the rejected receipt as an artifact
- emits a founder-visible system audit observation

This keeps replay honest: we can see both that a worker returned and why the
system refused to honor it.

## Risk posture after Step 18

- `RISK-0046` is addressed in current scope by thresholded renewal
- `RISK-0047` is addressed in current scope by unique-row + CAS-style claim
  updates
- `RISK-0048` is addressed in current scope by stale-result fencing and
  pessimistic reclaim
- `RISK-0050` is addressed by using store/server time as the only lease truth
- remaining follow-on risks are:
  - `RISK-0049`
  - `RISK-0051`
