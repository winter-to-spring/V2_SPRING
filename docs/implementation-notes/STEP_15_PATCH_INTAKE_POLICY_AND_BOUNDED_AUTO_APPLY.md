# Step 15 - Patch Intake Policy Routing And Bounded Auto-Apply

## Goal

Reduce founder review bottlenecks without weakening the strict patch intake
contract.

## What Changed

- patch intake policy now distinguishes between founder-review-only and bounded
  auto-apply candidates
- low-risk, explicitly `auto_apply_eligible` patch intakes may be applied
  automatically
- automatic application uses the same strict patch apply and bounded validation
  path as founder approval
- success and failure both produce replay-visible outcomes

## Policy Shape

The auto-apply lane is intentionally narrow.

Current eligible shape:

- low-risk patch intake
- single-file patch
- no dangerous keyword warning
- no sensitive path warning

Everything else remains founder-review gated by default.

## Resolution Semantics

### Auto-apply success

- patch intake status becomes `applied`
- resolution code becomes `AUTO_APPLIED`
- validation receipt artifact is written
- run transitions to `completed`
- system audit records the auto-apply event

### Auto-apply failure

- patch intake status becomes `rejected`
- rejection code is typed from strict apply / validation result
- run transitions back to `ready`
- replay and status surfaces show the failure

## Why This Is Safe

Auto-apply is not a bypass around trust.

It reuses the same:

- strict all-or-nothing patch apply
- bounded validation
- artifact preservation
- audit visibility

The only change is who triggers that strict gate:

- founder review for normal-risk lanes
- policy-controlled automatic approval for bounded low-risk lanes

## Follow-up

- broader trust scoring remains out of scope
- medium/high-risk auto-apply remains out of scope
- per-repo review policy customization remains out of scope

## Feedback Incorporated

- Review-fatigue feedback pushed this slice to open only a bounded auto-apply
  lane instead of broad review bypass.
- At the same time, trust feedback required auto-apply to reuse the exact same
  strict apply and validation path as founder-approved patches.
- That is why the policy narrows who can trigger the gate, not what the gate
  does.
