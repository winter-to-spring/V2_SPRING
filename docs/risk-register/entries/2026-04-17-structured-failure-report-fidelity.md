# Risk ID: RISK-0015
Title: Structured failure reports may still hide the root cause the planner needs
Class: Before Next Phase
Status: Mitigating
Owner: Core / Planner adapter
Observed In: Step 10 design and implementation

## Description

Step 10 replaces raw ledger input with a bounded structured failure report.

That is the right tradeoff for safety and cost, but it introduces a new
summarizer bottleneck:

- if the summarizer misses the meaningful error code
- or truncates the wrong part of the traceback
- or normalizes away the wrong distinction

the planner may receive a clean but misleading world model.

## Impact

- planner self-correction quality may collapse even though the transport works
- repeated bad replans may still happen under apparently "good" structured input
- debugging becomes harder because the wrong summary can look authoritative

## Why This Matters

Step 10 is the first point where the system, not the founder, decides what
planner-facing failure context looks like.

If that summary is wrong, the planner can become systematically dumb while the
typed contract still appears healthy.

## Suggested Mitigation

- keep error code and short traceback in the report
- preserve previous rationale and observed outcome side by side
- add targeted tests for common deterministic and transient failures
- revisit richer failure-report fidelity before real production traffic

Current mitigation:

- `FailureReportView` carries `failure_class`, `error_code`, `short_traceback`,
  `normalized_failure_signature`, `previous_rationale`, `observed_outcome`, and
  `repeated_failure_streak`
- planner context now includes the structured failure report directly
- regression tests cover stable classification for permission/path/timeout/rate
  limit style failures
- failure-report tests prove that previous planner rationale and sanitized
  tracebacks survive into planner context

## Capability Gate
- Capability: planner-backed tracer bullet / stronger replanning loop
- Gate mode: Before Next Phase
- Blocked until: failure-report fidelity is proven adequate for common failure modes

## Issue Link
- GitHub Issue: #19

## Doc Links
- ADR: ../../adr/0007-planner-decision-output-contract.md
- Design note: ../../implementation-notes/STEP_10_LANGGRAPH_PLANNER_ADAPTER.md

## Exit Criteria

- failure report preserves enough signal for planner self-correction in repeated tests
- common execution failures map to stable error codes and useful short traces
- planner-facing failure summaries remain sanitized and bounded

## Last Updated
- 2026-04-17
