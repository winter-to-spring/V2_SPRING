# [코어] Step 22 - Postgres contention soak + controller DB boundary hardening

## 배경 / 문제

Step 21을 통해 V2_SPRING은 PostgreSQL을 migration-controlled primary store로
다룰 준비를 갖췄습니다. 이제 Postgres는 더 이상 "옵션"이 아니라,
멀티워커/멀티에이전트 운영으로 가기 위한 현실적인 기반이 되었습니다.

하지만 아직 몇 가지 운영 리스크가 남아 있습니다.

- `RISK-0055` PostgreSQL connection exhaustion under worker/controller fanout
- `RISK-0057` Postgres write lock contention under claim/renew/audit load
- `RISK-0058` deadlock contention around multi-table transactional writes
- `RISK-0061` controller throughput / SPOF pressure under controller-mediated DB access

즉 Step 22의 목적은 새로운 기능을 여는 것이 아니라,
**"Postgres가 실제 fanout과 contention 상황에서도 control plane을 버틸 수 있는가"를
실증하는 것**입니다.

## 이번 단계의 목적

- controller-mediated DB access 원칙을 더 명확하게 고정합니다
- worker/container runtime이 직접 Postgres를 두드리지 않도록 trust boundary를 강화합니다
- live Postgres에서 claim / renew / reclaim / audit hot path contention smoke를 검증합니다
- connection pool과 transaction scope가 예상 fanout 아래에서 어떻게 동작하는지 확인합니다
- lock ordering과 transaction scope가 deadlock을 부르지 않도록 더 명시적으로 고정합니다
- founder/operator가 락 대기, pool 포화, transaction 지연 중 무엇이 문제인지 읽을 수 있게 합니다
- Step 21에서 mitigating으로 남긴 Postgres 운영 리스크를 실제로 더 줄입니다

## 구현 범위

- controller-only DB ownership 가드레일 명시 및 코드 경계 보강
- live Postgres contention / fanout smoke harness
- claim / renew / reclaim 경쟁 시나리오에 대한 regression test 보강
- connection pool visibility or doctor surface 보강
- lock waiting / transaction latency / contention summary 진단 표면 보강
- consistent locking order와 짧은 transaction scope를 문서/코드에 같이 고정
- contention 결과가 founder/operator 관점에서도 해석 가능하도록 audit/observation 개선
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- Redis queue / pubsub 도입
- network-open execution runtime 확장
- external side-effect fencing (`RISK-0051`) 완전 closure
- LangGraph Postgres persistence 확장

## Acceptance Criteria

- live Postgres에서 claim/renew/reclaim hot path가 contention smoke를 통과한다
- worker는 direct DB writer가 아니라 controller-mediated 경로만 사용한다
- connection pool 설정/행동이 fanout 상황에서 최소한의 운영 가시성을 가진다
- 락 대기 시간 / connection utilization / transaction latency 중 최소한 핵심 진단이 노출된다
- `RISK-0055`, `RISK-0057`, `RISK-0058`이 Step 22 범위에서 직접 줄거나 닫힌다
- `RISK-0061`은 Step 22에서 최소한 관측 가능성과 경계 규약이 강화된다
- founder/operator가 "DB는 붙었지만 지금 막히는 중인지"를 읽을 수 있는 최소 진단 표면이 있다

## 리스크 연결

- 직접 타깃:
  - `RISK-0055`
  - `RISK-0057`
  - `RISK-0058`
- 직접 완화:
  - `RISK-0061`
- 이번 단계에서 직접 다루지 않는 것:
  - `RISK-0051`
  - `RISK-0059`
  - `RISK-0060`
  - `RISK-0036`
  - `RISK-0045`
  - `RISK-0006`
  - `RISK-0026`
