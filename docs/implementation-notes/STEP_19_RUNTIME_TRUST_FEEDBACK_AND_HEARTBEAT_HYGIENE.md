# Step 19 - Runtime Trust Feedback And Heartbeat Hygiene

## What changed

- added typed runtime trust state for execution runtimes
- promoted containerized workers from static-only trust to
  evidence-driven trust
- added conservative strike-based promotion to dynamic preflight
- added recovery logic back to static-first mode
- tightened lease renewal cadence so repeated renew calls can be coalesced
- exposed runtime trust through the CLI and execution-claim surfaces

## Key policies

### Runtime trust

- default mode: `static_manifest`
- promotion threshold: `3` consecutive capability mismatches
- recovery threshold: `2` successful dynamic-preflight executions
- trust state is stored centrally, not inferred from local worker clocks or
  process-local caches

### Heartbeat hygiene

- expiry is computed from store/server time only
- renewals only write when the claim is inside the renew window
- renewals inside the minimum cadence window are coalesced into a read-only
  response

## Founder/operator impact

- `v2-spring runtime trust` now shows current trust mode and strike state
- execution claim surfaces now show renew threshold, renew cadence, and renewal
  pressure

## Risk impact

- `RISK-0039` is closed in the current containerized-runtime scope because
  observed runtime mismatch now changes future preflight behavior
- `RISK-0049` is closed in the current scope because healthy renewals are now
  coalesced instead of writing on every heartbeat
- `RISK-0051` remains deferred until networked or external-side-effect
  runtimes are opened

## Feedback Incorporated

- Runtime-trust feedback pushed this slice beyond static manifests into strike-
  based trust promotion and recovery.
- Operational feedback on heartbeat storms also drove the coalesced renewal
  cadence and founder-visible renewal pressure surface.
- The trust model stays centrally stored so one noisy worker cannot fork local
  truth.
