# ADR 0013: Patch Intake Policy Routing

## Status
Accepted

## Context

Step 12-c introduced a strict founder review gate for every worker-produced
patch. That was the right default for the first proof, but it leaves a clear
throughput bottleneck:

- low-risk single-file patches wait behind the same founder gate as risky ones
- execution-plane throughput becomes founder-attention bound
- the intake model already knows risk and eligibility, but policy was not using
  that information yet

## Decision

We introduce a bounded auto-apply lane for explicitly low-risk patch intakes.

The policy is intentionally narrow:

- only low-risk patch intakes may be considered
- only explicitly `auto_apply_eligible` intakes may use the lane
- auto-apply still runs the same strict patch apply and bounded validation used
  for founder approval
- all other patch classes remain founder-review gated

Auto-apply is therefore not a bypass around trust; it is a policy-controlled
reuse of the same strict gate under a narrower risk class.

## Consequences

### Positive

- low-risk execution results no longer always bottleneck on founder review
- replay and audit keep a first-class record of automatic application
- founder attention is preserved for medium/high-risk changes

### Negative

- intake policy is now more stateful and must be tested carefully
- future expansion of the auto-apply lane should remain explicit and narrow

## Follow-up

- broader trust/routing systems remain deferred
- review fatigue is resolved for the current bounded execution scope, not for all
  future worker classes by default
