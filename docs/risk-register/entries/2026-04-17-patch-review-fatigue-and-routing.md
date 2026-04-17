# Risk ID: RISK-0025
Title: Founder review may become a throughput bottleneck without risk-based patch intake routing
Class: Later Hardening
Status: Open
Owner: Intake gate / Founder surface
Observed In: Step 12-c patch intake planning

## Description

If every worker patch requires founder approval regardless of risk or scope,
the review gate can become the system bottleneck.

That is acceptable for an initial proof, but not for a broader execution plane
where many low-risk receipts may arrive.

## Impact

- founder attention becomes the slowest part of the system
- small safe changes wait behind large risky ones
- automation gains flatten because intake remains fully manual

## Why This Matters

The intake gate is essential for trust, but it should not force the same review
cost on all patch classes forever.

V2_SPRING needs a path toward bounded auto-apply for explicitly low-risk
results while keeping risky mutations review-gated.

## Suggested Mitigation

- include risk class and auto-apply eligibility metadata in patch intake
- keep founder review as the default for the first proof
- later open bounded auto-apply only for well-defined low-risk classes

## Capability Gate
- Capability: broader execution-plane throughput beyond initial worker proof
- Gate mode: Later Hardening
- Blocked until: intake policy can differentiate low-risk auto-apply candidates
  from founder-review-only patches

## Issue Link
- GitHub Issue: #30

## Doc Links
- ADR:
- Design note: ../../issues/STEP_12C_PATCH_INTAKE_REVIEW_GATE.md

## Exit Criteria

- patch intake carries explicit review policy metadata
- low-risk auto-apply policy can be added without redesigning the intake model

## Last Updated
- 2026-04-17
