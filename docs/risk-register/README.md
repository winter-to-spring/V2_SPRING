# Shared Risk Register

The risk register exists so operational and architectural risks do not live in
one person's memory.

If another agent, another teammate, or another session picks up this repo,
they should be able to answer three questions quickly:

1. What risks are already known?
2. When do they have to be fixed?
3. What capability should stay gated until they are fixed?

## Operating Rules

### 1. The register is a shared repo artifact

Every meaningful risk is recorded in this repo.

We do not rely on private memory, informal chat, or "we'll remember later"
promises.

### 2. Every risk gets a class

Use one of these classes:

- `Now`
- `Before Next Phase`
- `Before Scale`
- `Later Hardening`

### 3. Every risk gets a capability gate

The risk entry must say what it blocks.

Examples:

- opening planner/replanner
- adding background workers
- increasing agent count
- exposing a founder surface

### 4. Issues are for execution, not for memory

The risk register is the full shared memory.

GitHub issues are created when a risk becomes an execution slice:

- `Now`
- `Before Next Phase`
- repeated or cross-cutting risks
- anything that needs implementation rather than passive tracking

### 5. Resolved risks stay visible

Resolved risks are not deleted from this register.

We keep them visible with a strikethrough in the index and in the entry title so
future readers can see:

- what risk existed
- when it was noticed
- and that it was later resolved

### 6. Resolve timing follows capability gates, not vague calendar promises

We do not say "sometime later" without also saying:

- before which phase
- before which capability
- or before which scale jump

## Minimal Entry Template

```markdown
# Risk ID: RISK-0001
Title:
Class: Now | Before Next Phase | Before Scale | Later Hardening
Status: Open | Mitigating | Deferred | Resolved
Owner:
Observed In:

## Description

## Impact

## Why This Matters

## Suggested Mitigation

## Capability Gate
- Capability:
- Gate mode:
- Blocked until:

## Issue Link
- GitHub Issue:

## Doc Links
- ADR:
- Design note:

## Exit Criteria

## Last Updated
- YYYY-MM-DD
```

## Current Entries

- ~~[RISK-0001 Approval timeout / deadlock](entries/2026-04-16-approval-timeout.md)~~
- ~~[RISK-0002 Approval reject reason missing](entries/2026-04-16-approval-reject-reason.md)~~
- ~~[RISK-0003 Pending approval write barrier missing](entries/2026-04-16-pending-approval-write-barrier.md)~~
- ~~[RISK-0004 Service-level approval barrier race window](entries/2026-04-16-service-level-barrier-race-window.md)~~
- [RISK-0005 RunSnapshot staleness under concurrent writes](entries/2026-04-16-run-snapshot-staleness.md)
- [RISK-0006 Snapshot/action read-model growth](entries/2026-04-16-snapshot-read-model-growth.md)
- ~~[RISK-0007 Possible-actions engine purity drift](entries/2026-04-16-possible-actions-engine-purity.md)~~
- ~~[RISK-0008 Planner proposal loop lacks retry bounds and idempotency policy](entries/2026-04-16-planner-proposal-loop-control.md)~~
- ~~[RISK-0009 Planner-facing audit payload hygiene](entries/2026-04-16-planner-audit-payload-hygiene.md)~~
- ~~[RISK-0010 Phase budget reset abuse may refresh planner retries without meaningful progress](entries/2026-04-16-phase-budget-reset-abuse.md)~~
- ~~[RISK-0011 Manual recharge lacks environment preflight and misuse guardrails](entries/2026-04-16-manual-recharge-misuse.md)~~
- ~~[RISK-0012 Cognitive duplicate detection remains exact-fingerprint only](entries/2026-04-16-cognitive-duplicate-heuristic-limit.md)~~
- ~~[RISK-0013 Accepted legal proposals may loop through repeated execution failure without planner budget pressure](entries/2026-04-16-execution-failure-loop-escape.md)~~
- ~~[RISK-0014 Stale planner proposals currently consume phase budget even when the fault is systemic timing drift](entries/2026-04-16-stale-budget-penalty-fairness.md)~~
- ~~[RISK-0015 Structured failure reports may still hide the root cause the planner needs](entries/2026-04-17-structured-failure-report-fidelity.md)~~
- ~~[RISK-0016 Planner may escalate too early or too often once escalation becomes a legal output type](entries/2026-04-17-premature-escalation-thrash.md)~~
- ~~[RISK-0017 Founder reply semantics are still ambiguous after planner escalation](entries/2026-04-17-founder-reply-contract-ambiguity.md)~~
- ~~[RISK-0018 Founder reply CLI ergonomics may cause operator error before a richer surface exists](entries/2026-04-17-founder-reply-cli-ergonomics.md)~~
- ~~[RISK-0019 Single-provider structured output may leak vendor semantics into the core planner transport seam](entries/2026-04-17-provider-schema-lock-in.md)~~
- ~~[RISK-0020 Provider/network errors may bypass planner governance if they are not normalized at the adapter edge](entries/2026-04-17-provider-error-normalization-leak.md)~~
- [RISK-0021 Local CLI cancellation may leave an in-flight provider call orphaned after the terminal exits](entries/2026-04-17-provider-cancellation-orphan.md)
- [RISK-0022 Multi-worker approval gating still needs lease-aware concurrency controls](entries/2026-04-17-multi-worker-approval-concurrency.md)
- [RISK-0023 Isolated worker proof may leak secrets or main workspace access if isolation is only logical](entries/2026-04-17-isolated-worker-sandbox-leakage.md)
- [RISK-0024 Isolated worker may crash or hang without a reclaim path, leaving running tasks stuck](entries/2026-04-17-silent-worker-crash-reclaim-gap.md)
- [RISK-0025 Founder review may become a throughput bottleneck without risk-based patch intake routing](entries/2026-04-17-patch-review-fatigue-and-routing.md)
- [RISK-0026 Explicit dispatcher rules may sprawl into a hard-to-audit routing blob as runtimes grow](entries/2026-04-17-routing-policy-sprawl.md)
