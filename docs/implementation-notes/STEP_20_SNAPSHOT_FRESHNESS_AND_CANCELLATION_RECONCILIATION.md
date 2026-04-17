# Step 20 - Snapshot Freshness And Cancellation Reconciliation

## What changed

- added `freshness_generation` to `RunSnapshotView`
- added typed snapshot freshness refusal models
- surfaced freshness anchors in progress and patch-review views
- wired freshness validation into:
  - `task dispatch`
  - `patch approve`
  - `patch reject`
- extended local planner cancellation from a single interrupt audit into:
  - cancellation intent
  - local reconciliation / bounded orphan-risk finalization

## Freshness contract

- founders and operators inspect a snapshot or patch review
- the rendered surface now exposes:
  - `snapshot_hash`
  - `freshness_generation`
- mutation commands must present those anchors back when they want freshness
  protection
- if the run changed in the meantime, the mutation is blocked through a typed
  stale-snapshot refusal instead of silently acting on old state

## Cancellation contract

- local `planner invoke` interruption still surfaces a typed transport
  cancellation
- Step 20 now records two separate audit observations:
  - the interrupt intent
  - the bounded local reconciliation state
- this keeps replay honest about the difference between "the CLI stopped
  waiting" and "the upstream provider definitely stopped work"

## Risk impact

- `RISK-0005` is resolved in the current founder/operator mutation scope
  because stale snapshot use now yields a typed refusal before dispatch or patch
  mutation proceeds
- `RISK-0021` remains mitigating because local cancellation is now better
  classified and finalized, but remote provider orphan exposure still exists
  before scale
