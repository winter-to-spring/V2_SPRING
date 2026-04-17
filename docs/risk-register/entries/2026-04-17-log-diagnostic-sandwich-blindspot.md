# Risk ID: RISK-0038
Title: ~~Tail-only log hygiene may hide the real root cause when failures originate at process startup~~
Class: Before Next Phase
Status: Resolved
Owner: Execution plane / Runtime diagnostics
Observed In: Step 14 bounded log hygiene planning

## Description

Tail-first log capture is better than unbounded log copy-out, but it still has a
blind spot: some failures happen near process start, while the end of the log is
filled with repeated retries or noisy fallout.

If the bounded capture only preserves the tail, the operator may see plenty of
recent text but miss the real cause.

## Impact

- founder/operator sees bounded logs but still lacks root-cause visibility
- failure triage becomes slower even though log volume is controlled
- planners receive degraded failure reports and may replan poorly

## Why This Matters

Step 14 is supposed to improve both boundedness and diagnosability. A log policy
that protects the host but blinds operators only solves half the problem.

## Suggested Mitigation

- prefer a sandwich capture strategy such as `head + tail`
- keep overflow receipts explicit when full logs are too large to retain
- preserve enough startup evidence to explain environment/config failures

Current resolution:

- the container runtime now captures bounded diagnostics with a sandwich
  strategy
- receipts preserve startup and shutdown evidence together
- operators no longer depend on tail-only previews for root-cause visibility

Operational priority: medium. This should be absorbed in Step 14, but it is not
as foundational as metadata-registry determinism.

## Capability Gate
- Capability: Step 14 bounded log hygiene
- Gate mode: Before Next Phase
- Blocked until: bounded log capture preserves useful startup and shutdown
  diagnostics together

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR: ../../adr/0012-container-runtime-provenance-and-guardrails.md
- Design note: ../../implementation-notes/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## Exit Criteria

- bounded log capture is not tail-only
- oversized logs still preserve actionable startup and shutdown evidence
- failure receipts stay diagnosable without full raw log access

## Last Updated
- 2026-04-17
- 2026-04-17 (resolved in Step 14)
