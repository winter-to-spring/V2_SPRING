# Risk ID: RISK-0055
Title: worker/controller fanout이 커질 때 PostgreSQL connection exhaustion이 나타날 수 있음
Class: Before Next Phase
Status: Mitigating
Owner: Storage / Execution plane
Observed In: Step 21 planning

## 설명

V2_SPRING이 SQLite-first 로컬 실행에서 PostgreSQL 기반 multi-writer 실행으로
이동하면, 부주의한 connection ownership이 새로운 장애 모드가 될 수 있습니다.

worker, container, 또는 여러 controller process가 직접 DB 연결을 공격적으로
열기 시작하면 connection pool이 빠르게 포화될 수 있습니다.

## 영향

- claim, renewal, reconciliation이 pool exhaustion 때문에 막힐 수 있음
- 애플리케이션 코드는 멀쩡해도 founder/operator CLI가 불안정해 보일 수 있음
- background execution fanout이 전체 control plane을 느리게 만들 수 있음

## 왜 중요한가

Postgres는 transactional correctness를 해결해주지만, 접근 패턴이 충분히
절제되어야만 부하 상황에서도 저장소 가용성을 유지할 수 있습니다.

## 권장 완화책

- 기본적으로 DB 접근을 controller-mediated로 유지한다
- 명시적인 SQLAlchemy pool sizing과 overflow limit를 설정한다
- isolated/containerized worker가 Postgres에 직접 접근하지 못하게 한다
- fanout을 재현하고 pool pressure를 관측하는 운영 테스트를 추가한다

현재 완화 상태:

- Step 21은 pool pre-ping이 켜진 PostgreSQL 전용 engine 기본값을 추가함
- controller-mediated DB access가 기본 경계로 유지되며, 이 단계에서 worker는
  direct ledger write를 얻지 못함
- migration issue는 이제 connection ownership을 부수 고려사항이 아니라
  핵심 설계 제약으로 다룸
- Step 22는 `v2-spring doctor`를 통해 pool sizing, checked-out connection,
  overflow, utilization을 노출함
- Step 22는 live PostgreSQL contention smoke probe를 추가해 pool pressure를
  가정이 아니라 실제 관측 대상으로 만듦

## Capability Gate
- Capability: multi-worker / multi-agent execution on Postgres
- Gate mode: Before Next Phase
- Blocked until: controller-mediated connection ownership and bounded pool
  behavior are implemented

## Issue Link
- GitHub Issue: #47

## Doc Links
- ADR: ../../adr/0019-postgres-migration-and-transactional-concurrency.md
- ADR: ../../adr/0020-postgres-contention-soak-and-controller-boundary.md
- Design note: ../../issues/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_21_POSTGRES_MIGRATION_AND_TRANSACTIONAL_CONCURRENCY.md
- Design note: ../../implementation-notes/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## 종료 기준

- worker fanout이 무제한 direct connection으로 primary DB를 고갈시키지 못한다
- controller pool 동작이 예상 부하 아래에서 설정되고 검증된다

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating in Step 21)
- 2026-04-17 (mitigating with Step 22 doctor diagnostics and live contention smoke)
