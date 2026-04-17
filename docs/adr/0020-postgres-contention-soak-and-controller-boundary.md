# ADR 0020: Postgres Contention Soak And Controller Boundary

## Status

Accepted

## Context

Step 21 proved that V2_SPRING can bootstrap against PostgreSQL through
migration-controlled startup.

That was necessary, but not sufficient, for opening a healthier multi-writer
future. The next question was operational rather than structural:

- can claim / renew / reclaim hot paths survive real lock contention?
- can founder/operator tooling tell the difference between pool pressure and
  lock pressure?
- can we preserve the controller-owned DB trust boundary while doing so?

## Decision

We adopt the following Step 22 rules:

1. Database ownership remains controller-mediated; workers do not gain direct
   Postgres credentials.
2. Postgres diagnostics become a first-class `doctor` surface rather than a
   private operator script.
3. Claim mutation hot paths converge on a more consistent locking order:
   run row first, claim row second.
4. A live PostgreSQL contention smoke harness becomes part of the storage
   verification story.
5. Deadlock avoidance is treated as a correctness concern, not merely a
   performance concern.

## Consequences

### Positive

- founder/operator tooling can now see live lock waiting and pool pressure
- Postgres contention is exercised intentionally instead of being discovered by
  accident
- controller-owned DB access is easier to explain and defend operationally
- Step 22 gives a concrete burn-down path for `RISK-0058`

### Negative

- the storage layer now carries more diagnostic-specific code
- the doctor surface is more complex because it reports runtime state, not just
  bootstrap state
- connection pressure and controller throughput still require future hardening

## Follow-on

- keep `RISK-0055` and `RISK-0057` mitigating until broader contention/load
  envelopes are proven
- keep `RISK-0061` mitigating until controller throughput is better bounded
- defer `RISK-0059` and `RISK-0060` until scale-oriented storage tuning work
