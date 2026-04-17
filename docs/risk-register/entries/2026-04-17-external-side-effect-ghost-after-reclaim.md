# Risk ID: RISK-0051
Title: stale result를 fencing해도 reclaim된 lease 이후 외부 side-effect는 계속 남을 수 있음
Class: Before Scale
Status: Mitigating
Owner: Runtime isolation / external side-effect contracts
Observed In: Step 18 fenced reclaim hardening

## 설명

Step 18은 reclaim 이후 stale result를 거부할 수 있지만, 이미 worker boundary
밖으로 빠져나간 side-effect를 자동으로 되돌리지는 못합니다.

미래 runtime이 외부 API를 호출하거나 원격 시스템을 변경하거나 로컬 bounded
workspace 밖에 영향을 주기 시작하면, reclaim은 결과 수용만 막고 외부 변경
자체는 완전히 막지 못할 수 있습니다.

## 영향

- ledger상 reclaim은 올바르게 보여도 외부 시스템은 계속 drift할 수 있음
- 내부 상태는 fenced되어도 중복되거나 stale한 외부 작업은 계속 살아남을 수 있음
- control plane이 실제보다 더 강력해 보이면서 founder/operator 신뢰를 해칠 수 있음

## 왜 중요한가

control plane을 fencing하는 것은 필요하지만, control plane 바깥 세계를
fencing하는 것과는 다릅니다.

V2_SPRING이 실제 외부 변경 surface를 가진 runtime을 여는 순간, lease reclaim은
로컬 결과 거부를 넘어서야 합니다.

## 권장 완화책

- 가능하면 fencing/idempotency token을 외부 시스템에도 전달한다
- 명시적인 외부 idempotency contract가 있을 때만 networked/side-effect runtime을 연다
- 원격 시스템이 제공할 수 있다면 side-effect 전후 receipt를 비교한다
- 그런 계약이 생길 때까지 현재 container runtime은 `--network none`으로 유지한다

현재 완화 상태:

- 현재 bounded container worker는 `--network none`으로 동작함
- reclaim은 pessimistic하게 유지되며 hard container kill을 시도함
- stale local result는 reclaim 또는 supersession 이후 거부됨

## Capability Gate
- Capability: networked runtimes / external API mutation / remote side-effectful
  workers
- Gate mode: Before Scale
- Blocked until: external side-effects can be fenced or deduplicated with the
  same rigor as local result submission

## Issue Link
- GitHub Issue: #43

## Doc Links
- ADR: ../../adr/0016-lease-renewal-fencing-and-stale-result-rejection.md
- Design note: ../../implementation-notes/STEP_18_LEASE_RENEWAL_AND_FENCED_RECLAIM_HARDENING.md

## 종료 기준

- networked runtime이 fencing/idempotency evidence를 외부 시스템으로 전달한다
- reclaim semantics가 로컬 result 거부와 외부 effect cutoff를 함께 설명할 수 있다
- 원격 side-effect가 명시적 audit evidence 없이 reclaim 이후 살아남지 않는다

## Last Updated
- 2026-04-17
