# Risk ID: RISK-0020
Title: ~~Provider/network errors may bypass planner governance if they are not normalized at the adapter edge~~
Class: Before Next Phase
Status: Resolved
Owner: Core / Planner transport
Observed In: Step 10-c production transport design review

## Description

Different model providers surface failures differently:

- timeouts
- rate limits
- transient 5xx responses
- structured output refusals
- SDK-specific transport exceptions

If Step 10-c lets those raw exceptions leak into the application layer, the
planner governance contract can misclassify them, fail to apply bounded retry,
or crash the CLI entirely.

## Impact

- retries may happen on the wrong failure class
- planner budget and stale quota policies may be applied unfairly
- production invokes may crash instead of producing replayable audit evidence

## Why This Matters

The point of Step 10-c is not only to call a real LLM, but to keep provider and
network instability outside the control-plane core.

If error translation is weak, the transport boundary stops being a boundary.

## Suggested Mitigation

- normalize provider exceptions into internal typed transport errors
- separate provider/network retries from planner logic retries
- capture token usage and failure metadata even for bounded provider failures
- make cancellation/timeout/orphan behavior explicit in the transport layer

This slice resolves the adapter-edge normalization requirement by:

- introducing typed transport failures (`timeout`, `rate_limit`, `network`,
  `provider_unavailable`, `authentication`, `provider_response`, `cancelled`)
- keeping provider exceptions behind the OpenAI-specific transport
- recording bounded provider/network failures as replayable `SYSTEM_AUDIT`
  observations instead of letting raw SDK exceptions leak into the CLI
- separating provider/network retry from planner-phase budget accounting

## Capability Gate
- Capability: real production planner transport
- Gate mode: Before Next Phase
- Blocked until: provider/network failure classes are translated into internal
  transport errors and handled without leaking SDK-specific exceptions

## Issue Link
- GitHub Issue: #23

## Doc Links
- ADR: ../../adr/0009-production-planner-transport-seam.md
- Design note: ../../implementation-notes/STEP_10C_PRODUCTION_TRANSPORT_HARDENING.md

## Exit Criteria

- provider exceptions do not leak past the adapter boundary
- retry/backoff policy is driven by internal transport error classes
- transport failures leave replayable audit evidence instead of opaque crashes

## Last Updated
- 2026-04-17
