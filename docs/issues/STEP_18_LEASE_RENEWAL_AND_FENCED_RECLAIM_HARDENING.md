# [코어] Step 18 - Lease renewal + atomic claims + fenced reclaim hardening

## 배경 / 문제

Step 17에서 execution claim 모델과 pessimistic reclaim을 도입하면서,
현재 스코프의 execution ownership은 크게 안정화되었습니다.

하지만 lease 모델에는 아직 다음 hardening 포인트가 남아 있습니다.

- bounded TTL만으로는 더 긴 execution lane을 안전하게 다루기 어렵다
- claim acquisition은 현재 store/transaction 성질에 부분적으로 의존한다
- reclaim은 현재 runtime-specific hard kill 시도를 하지만, fencing 보장이
  더 명시적이어야 한다

즉 Step 18의 목적은 새로운 worker를 여는 것이 아니라,
**이미 도입한 execution lease를 더 믿을 수 있게 만드는 것**입니다.

## 이번 단계의 목적

- lease renewal / heartbeat semantics를 도입합니다
- claim acquisition의 atomicity contract를 더 명시적으로 강화합니다
- reclaim 이후 stale owner 결과를 더 강하게 배제하는 fencing contract를 만듭니다
- reclaim / renewal / expiry lifecycle을 founder-visible하게 유지합니다
- Step 17에서 열린 lease hardening 리스크를 **실제로 줄이는 단계**로 가져갑니다

## 구현 범위

- active claim heartbeat/renew path
- worker local clock가 아니라 **store/server time 기준** renewal/expiry 판단
- 남은 TTL이 충분할 때는 쓰지 않는 **thresholded renewal** 규칙
- bounded lease renewal rules
- claim version / fencing token contract 강화
- atomic claim reacquire/update path를 version-gated compare-and-swap로 강화
- reclaim 이후 stale completion/result rejection
- runtime-specific reclaim evidence를 receipt/audit로 연결
- CLI/status/replay에서 renewal / expiry / reclaim 히스토리 노출
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- full distributed queue broker
- multi-region scheduler
- generalized remote callback bus
- image-pool / cold-pull optimization

## Acceptance Criteria

- longer-running bounded execution이 lease renewal 없이 쉽게 만료되지 않는다
- competing claim acquisition semantics가 더 명시적으로 보인다
- reclaimed execution의 late result는 accepted path로 돌아오지 못한다
- reclaim / renewal / expiry가 replay와 founder surface에서 추적 가능하다
- 테스트로 renewal, stale late result rejection, fenced reclaim 경계를 증명한다
- `RISK-0046`, `RISK-0047`, `RISK-0048`가 Step 18 범위에서 직접 줄거나 닫힌다
- `RISK-0050` clock drift는 Step 18 설계에 흡수되어 resolved 상태로 남는다
- `RISK-0049`, `RISK-0051`은 남더라도 follow-on risk로 분리되어
  현재 경계와 다음 hardening 경계를 혼동하지 않게 한다

## 리스크 연결

- 직접 타깃:
  - `RISK-0046` lease starvation / reclaim deadlock
  - `RISK-0047` atomic claim failure
  - `RISK-0048` reclaim side-effects without fencing
- 이번 단계에서 설계에 흡수하고 등록/정리하는 것:
  - `RISK-0050` clock drift
    - worker clock는 신뢰하지 않고 store/server time만 expiry truth로 사용
    - Step 18에서 resolved 상태로 남긴다
- 이번 단계 후 follow-on으로 남길 수 있는 것:
  - `RISK-0049` heartbeat storm
  - `RISK-0051` external side-effect ghost
- 후속으로 남는 것:
  - `RISK-0039` manifest vs runtime reality gap
  - `RISK-0036` image bloat / pull latency
  - `RISK-0026` routing policy sprawl

## 연결 문서

- `docs/issues/STEP_17_EXECUTION_LEASES_AND_ORPHAN_RECONCILIATION.md`
- `docs/adr/0015-lease-aware-execution-claims-and-reclaim.md`
- `docs/risk-register/entries/2026-04-17-lease-starvation-and-reclaim-deadlock.md`
- `docs/risk-register/entries/2026-04-17-atomic-claim-failure.md`
- `docs/risk-register/entries/2026-04-17-reclaim-side-effects-without-fencing.md`
