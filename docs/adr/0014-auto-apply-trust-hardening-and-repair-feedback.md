# ADR 0014: Auto-Apply Trust Hardening And Repair Feedback

## Status
Accepted

## Context

Step 15 opened a bounded auto-apply lane for low-risk patch intake results.
That removed the founder bottleneck for obviously safe changes, but it also
exposed new trust gaps:

- semantically central files could still look small enough for auto-apply
- the planner could slice one risky change into many trivial patches
- simple keyword scans could miss obfuscated dangerous patterns
- detailed validation feedback could improve repair quality while still letting
  the planner burn time in a bounded but wasteful retry loop

## Decision

We harden the bounded auto-apply lane with explicit, replay-visible rules.

The policy now includes:

- central/protected file detection that forces founder review even for
  single-file, low-line-count patches
- burst detection for repeated auto-apply against the same file or module over a
  bounded window
- lightweight structural scan that separates hard block findings from soft
  warning findings
- detailed patch repair feedback built from strict apply and validation receipts
- bounded repair retry quota that escalates to founder guidance when repeated
  repair attempts do not converge

We keep this first implementation explicit and deterministic rather than
score-based.

## Consequences

### Positive

- the auto-apply lane remains narrow and easier to trust
- replay and founder surfaces can explain why auto-apply was blocked or
  rerouted
- failed auto-apply attempts give the planner materially better repair context
- repeated repair failure no longer hides behind silent background retry

### Negative

- patch policy logic becomes more stateful and must stay heavily tested
- static central-file rules still leave some shadow centrality unmodeled
- structural scan remains intentionally lightweight and conservative

## Follow-up

- richer centrality beyond static protected-file rules remains deferred
- stronger semantic analysis remains deferred
- broader trust expansion should stay explicit and bounded rather than implicit
