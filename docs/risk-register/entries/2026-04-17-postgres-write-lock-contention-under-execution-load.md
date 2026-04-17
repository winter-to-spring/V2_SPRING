# Risk ID: RISK-0057
Title: claim과 renewal 부하 아래에서 Postgres write lock contention이 execution throughput을 떨어뜨릴 수 있음
Class: Before Next Phase
Status: Mitigating
Owner: Storage / Execution plane
Observed In: Step 21 planning

## 설명

Postgres는 V2_SPRING에 더 강한 transactional guarantee를 주지만, claim,
renewal, event write가 같은 row나 index에서 과하게 경합하면 lease와 audit
설계 자체가 비효율적일 수 있습니다.

특히 heartbeat/renew traffic과 execution-claim update가 일반 audit write와
섞이기 시작하면 이런 일이 더 잘 발생합니다.

## 영향

- worker concurrency 아래에서 claim acquisition latency가 급등할 수 있음
- 정상적인 renewal이 unrelated founder/operator flow를 느리게 만들 수 있음
- control plane은 논리적으로 맞더라도 운영적으로 둔해질 수 있음

## 왜 중요한가

정확성은 Step 21의 첫 목표지만, multi-writer execution이 더 넓게 열렸을 때도
쓸 수 있는 경로가 필요합니다.

## 권장 완화책

- Step 19의 thresholded renewal semantics를 유지한다
- claim lookup, expiry, active-claim check용 index를 명시적으로 설계한다
- targeted concurrency test로 high-contention path를 검증한다
- claim/reclaim hot path에서는 짧은 transaction과 좁은 lock scope를 선호한다

현재 완화 상태:

- Step 21은 claim acquisition, renewal, reclaim path에 Postgres-aware row locking을 추가함
- execution-claim table은 이제 status/expiry, runtime/status lookup용
  Postgres 친화 index를 명시적으로 가짐
- targeted regression test가 generated locking SQL과 ledger에서 쓰는 JSONB
  variant를 검증함
- Step 22는 release/reclaim hot path 전반에 걸쳐 run-first / claim-second lock
  ordering을 더 명시적으로 만듦
- Step 22는 실제 PostgreSQL 백엔드에서 lock waiting과 contender latency를
  측정하는 live contention smoke probe를 추가함

## Capability Gate
- Capability: multi-writer execution with Postgres as the primary store
- Gate mode: Before Next Phase
- Blocked until: claim/renew/reclaim paths demonstrate bounded contention under
  expected concurrency

## Issue Link
- GitHub Issue: #47

## Doc Links
- ADR: ../../adr/0019-postgres-migration-and-transactional-concurrency.md
- ADR: ../../adr/0020-postgres-contention-soak-and-controller-boundary.md
- Design note: ../../issues/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## 종료 기준

- claim과 renewal hot path가 명시적인 index/transaction 전략을 가진다
- concurrency regression test가 수용 가능한 contention 동작을 보여준다

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating in Step 21)
- 2026-04-17 (mitigating with Step 22 contention diagnostics and lock-order hardening)
