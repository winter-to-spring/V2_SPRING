# [코어] Step 21 - Postgres migration + transactional concurrency hardening

## 배경 / 문제

Step 20까지 오면서 planner/control plane, execution routing, container runtime,
lease fencing, runtime trust, snapshot freshness, cancellation reconciliation은
현재 로컬 단일 노드 스코프에서 꽤 단단해졌습니다.

하지만 실제 다중 에이전트/다중 워커 운영으로 넘어가려면, 현재의
SQLite-first 운영 모델은 동시 write, row-level contention, transactional
claim semantics 측면에서 한계가 명확합니다.

즉 Step 21의 목적은 새로운 기능을 여는 것이 아니라,
**실제 멀티에이전트 운영을 버틸 수 있는 주 저장소와 트랜잭션 경계로
코어를 옮기는 것**입니다.

## 이번 단계의 목적

- SQLite-first 로컬 모델에서 Postgres-first 운영 모델로 전환합니다
- execution claim / renew / reclaim / patch intake의 transactional 경계를
  Postgres semantics 위에 다시 고정합니다
- founder/operator CLI와 replay 모델은 그대로 유지하면서 저장소만 더 강한
  동시성 친화 계층으로 옮깁니다
- 다중 writer 환경에서 필요한 atomic mutation 패턴을 명확히 합니다
- Step 17-18에서 설계한 lease / fencing / reclaim 규칙을 Postgres의
  transaction과 row-level locking 위에서 물리적으로 고정합니다
- 리스크 장부에서 실제로 줄일 수 있는 concurrency-related risk를 직접 깎습니다

## 구현 범위

- Postgres `DATABASE_URL` 공식 지원 경로
- Alembic 기반 schema migration baseline
- local/dev migration guidance 및 bootstrap
- Postgres에서는 implicit ORM bootstrap을 금지하고 migration-controlled
  bootstrap만 허용
- founder/operator가 현재 DB dialect와 migration 상태를 읽을 수 있는
  doctor/status surface
- transactional execution claim acquire / renew / reclaim hardening
- row-level lock 또는 이에 준하는 stronger mutation guard
- audit ledger / event write path의 Postgres 호환성 검증
- stale snapshot / cancellation reconciliation이 Postgres transaction 경계에서
  어떻게 동작하는지 재정의
- concurrency regression test 추가
- ADR / implementation note / risk register 반영

## 권장 구현 순서

1. 실행 임차권(Execution leases / claims / reclaim) hot path부터 Postgres에 맞게 고정
2. 감사 원장(Audit ledger / event write path)과 replay 경로를 Postgres에서 검증
3. LangGraph state persistence는 후속 slice로 연결하되, 이번 단계에선 직접 범위로
   잡지 않음

## 이번 단계에서 하지 않는 것

- Redis queue / pubsub 도입
- distributed multi-region scheduler
- 성능 최적화만을 위한 read-cache 계층

## Acceptance Criteria

- Postgres를 주 저장소로 사용했을 때 CLI와 core flow가 정상 동작한다
- Postgres 경로는 migration이 없으면 fail-closed 하며 drift-prone implicit
  table creation을 하지 않는다
- execution claim 관련 경로가 stronger transactional semantics를 가진다
- schema migration 이력이 Alembic 등 코드 기반 도구로 관리된다
- SQLite에서는 애매했던 동시 mutation 경계가 Postgres 기준으로 명시된다
- multi-agent / multi-writer 확장 전에 필요한 저장소 기반이 준비된다
- concurrency-related risk가 Step 21 범위에서 직접 줄거나 닫힌다

## 리스크 연결

- 직접 타깃:
  - `RISK-0055` PostgreSQL connection exhaustion under worker/controller fanout
  - `RISK-0056` Schema drift during Postgres migration without versioned migration control
  - `RISK-0057` Write lock contention around claims, renewals, and audit writes under Postgres
- 저장소/동시성 측면에서 직접 줄이는 것:
  - stronger transactional mutation boundaries
  - atomic claim / renew / reclaim semantics under multi-writer load
  - controller-mediated DB access as the default trust boundary
- 이번 단계에서 직접 다루지 않는 것:
  - `RISK-0021` local CLI cancellation orphan
  - `RISK-0026` routing policy sprawl
  - `RISK-0036` container image bloat / pull latency
  - `RISK-0045` shadow centrality beyond protected paths
  - `RISK-0051` external side-effect ghost
