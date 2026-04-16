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

### 5. Resolve timing follows capability gates, not vague calendar promises

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

- [RISK-0001 Approval timeout / deadlock](entries/2026-04-16-approval-timeout.md)
- [RISK-0002 Approval reject reason missing](entries/2026-04-16-approval-reject-reason.md)
- [RISK-0003 Pending approval write barrier missing](entries/2026-04-16-pending-approval-write-barrier.md)
