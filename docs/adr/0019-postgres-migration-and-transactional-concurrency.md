# ADR 0019: Postgres Migration과 Transactional Concurrency

## 상태

Accepted

## 배경

Step 20 시점의 V2_SPRING은 강한 single-node control plane을 갖췄지만, primary
store semantics는 여전히 사실상 SQLite-first였습니다.

이것은 로컬 개발과 bounded founder/operator loop에는 충분했지만, 아래를 위한
건강한 기반은 아니었습니다.

- multi-writer claim / renew / reclaim traffic
- execution lease 주변의 row-level ownership semantics
- 장수하는 operational ledger를 위한 versioned schema evolution

Step 21은 storage layer를 Steps 17-20에서 이미 설계한 concurrency model과
맞추기 위해, 첫 번째 Postgres-oriented slice를 도입합니다.

## 결정

Step 21의 baseline을 아래와 같이 채택합니다.

1. multi-writer operation의 intended primary store는 PostgreSQL이다
2. execution-claim hot path는 dialect-aware row-lock helper를 가지며,
   Postgres는 `FOR UPDATE` semantics로 claim ownership을 강제한다
3. JSON-heavy ledger payload는 SQLite compatibility를 유지하면서도
   PostgreSQL JSONB variant를 사용한다
4. Alembic을 공식 schema-versioning 경로로 도입한다
5. migration 첫 대상은 lease / claim / reclaim path이고, LangGraph persistence는
   core ledger semantics가 Postgres에서 안정된 뒤로 미룬다

## 결과

### 긍정적

- lease와 fencing logic이 Postgres 위에서 더 명확한 storage contract를 가진다
- audit payload가 Postgres의 indexed JSON query에 더 잘 맞는다
- schema evolution이 implicit ORM bootstrap 대신 versioned migration baseline을 갖는다
- Step 21은 현재 single-node 동작과 미래 multi-agent execution 사이의 간극을 줄인다

### 부정적

- 저장소에 유지보수해야 할 Alembic scaffolding이 추가된다
- row-locking path가 store에 dialect-specific behavior를 더한다
- connection pool sizing과 lock contention은 여전히 runtime observation과
  follow-on hardening이 필요하다

## 후속

- Postgres-backed runtime behavior가 end-to-end로 증명될 때까지
  `RISK-0055`, `RISK-0056`, `RISK-0057`은 mitigating 상태로 유지한다
- networked runtime이 의도적으로 열리기 전까지 planner/runtime side-effect
  리스크는 범위 밖으로 둔다
