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
- ~~[RISK-0022 Multi-worker approval gating still needs lease-aware concurrency controls](entries/2026-04-17-multi-worker-approval-concurrency.md)~~
- ~~[RISK-0023 Isolated worker proof may leak secrets or main workspace access if isolation is only logical](entries/2026-04-17-isolated-worker-sandbox-leakage.md)~~
- ~~[RISK-0024 Isolated worker may crash or hang without a reclaim path, leaving running tasks stuck](entries/2026-04-17-silent-worker-crash-reclaim-gap.md)~~
- ~~[RISK-0025 Founder review may become a throughput bottleneck without risk-based patch intake routing](entries/2026-04-17-patch-review-fatigue-and-routing.md)~~
- [RISK-0026 Explicit dispatcher rules may sprawl into a hard-to-audit routing blob as runtimes grow](entries/2026-04-17-routing-policy-sprawl.md)
- ~~[RISK-0027 Soft-isolated worker proof lacks OS/container-level isolation for unrestricted bypass safety](entries/2026-04-17-lack-of-os-level-worker-isolation.md)~~
- ~~[RISK-0028 Patch may apply syntactically while still introducing semantic or validation-breaking drift](entries/2026-04-17-patch-semantic-conflict-after-apply.md)~~
- ~~[RISK-0029 Founder review may miss dangerous or over-broad patch changes without guided review signals](entries/2026-04-17-patch-review-danger-blindness.md)~~
- ~~[RISK-0030 Containerized worker may escape isolation if docker socket or privileged mode is exposed](entries/2026-04-17-docker-socket-and-privileged-container-escape.md)~~
- ~~[RISK-0031 Containerized worker artifacts may be unreadable or undeletable on the host due to UID/GID mismatch](entries/2026-04-17-container-artifact-ownership-mismatch.md)~~
- ~~[RISK-0032 Containerized worker may leave orphan containers behind after interruption or crash](entries/2026-04-17-container-orphan-garbage-collection-gap.md)~~
- ~~[RISK-0033 Containerized worker image tags may drift and break deterministic replay without digest-pinned provenance](entries/2026-04-17-container-image-integrity-and-replay-drift.md)~~
- ~~[RISK-0034 Containerized worker log explosion may exhaust host disk during copy-out or receipt collection](entries/2026-04-17-container-log-explosion-and-copy-out-disk-risk.md)~~
- ~~[RISK-0035 Containerized worker capability expansion may fail because runtime dependencies diverge from host assumptions](entries/2026-04-17-container-runtime-environment-gap.md)~~
- [RISK-0036 Container worker image growth may inflate pull latency and erode execution-plane responsiveness](entries/2026-04-17-container-image-bloat-and-pull-latency.md)
- ~~[RISK-0037 Local metadata snapshots may drift across environments and make routing decisions non-deterministic](entries/2026-04-17-metadata-snapshot-fragmentation.md)~~
- ~~[RISK-0038 Tail-only log hygiene may hide the real root cause when failures originate at process startup](entries/2026-04-17-log-diagnostic-sandwich-blindspot.md)~~
- [RISK-0039 Static capability manifests may drift away from actual runtime health and create false preflight confidence](entries/2026-04-17-manifest-reality-gap.md)
- ~~[RISK-0040 Semantic chain reaction may bypass founder review when low-risk auto-apply touches central files](entries/2026-04-17-semantic-chain-reaction-on-auto-apply.md)~~
- ~~[RISK-0041 Planner may game bounded auto-apply by slicing one risky change into many trivial patches](entries/2026-04-17-auto-apply-salami-attack.md)~~
- ~~[RISK-0042 Obfuscated dangerous patterns may bypass simple keyword scans in bounded auto-apply](entries/2026-04-17-obfuscated-dangerous-pattern-bypass.md)~~
- ~~[RISK-0043 Detailed repair feedback may still trap the planner in a bounded but wasteful repair loop](entries/2026-04-17-repair-loop-deadlock-after-detailed-feedback.md)~~
- ~~[RISK-0044 Lightweight structural scan may create founder friction through false positives](entries/2026-04-17-structural-scan-false-positive-friction.md)~~
- [RISK-0045 Static protected-path lists may miss semantically central files outside the initial trust boundary](entries/2026-04-17-shadow-centrality-beyond-protected-paths.md)
- ~~[RISK-0046 Lease TTL may starve long-running work or delay reclaim when ownership lasts too long](entries/2026-04-17-lease-starvation-and-reclaim-deadlock.md)~~
- ~~[RISK-0047 Execution claim acquisition may still depend on store-level serialization without stronger atomic CAS semantics](entries/2026-04-17-atomic-claim-failure.md)~~
- ~~[RISK-0048 Reclaim may reopen ownership before old worker side-effects are fully fenced](entries/2026-04-17-reclaim-side-effects-without-fencing.md)~~
- [RISK-0049 Lease renewal heartbeats may amplify control-plane write load as worker count grows](entries/2026-04-17-heartbeat-storm-under-lease-renewal.md)
- ~~[RISK-0050 Lease expiry may become non-deterministic when worker clocks drift from store/server time](entries/2026-04-17-clock-drift-in-lease-expiry.md)~~
- [RISK-0051 External side-effects may outlive reclaimed lease ownership even when stale results are fenced](entries/2026-04-17-external-side-effect-ghost-after-reclaim.md)
