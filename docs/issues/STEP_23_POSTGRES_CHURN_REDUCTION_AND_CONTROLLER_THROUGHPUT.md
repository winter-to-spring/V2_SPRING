# [engine] [코어] Step 23 - Postgres churn 축소 + audit 보존 정책 + controller 처리량 하드닝

## 배경 / 문제

Step 21은 PostgreSQL migration-controlled bootstrap을 열었고,
Step 22는 live contention과 controller DB boundary를 실제로 관측할 수 있게
만들었습니다.

이제 남은 문제는 "Postgres가 붙는다"가 아니라,
**"control plane이 불필요한 write churn 없이 오래 버티는가"** 입니다.

현재 남은 핵심 운영 리스크:

- `RISK-0055` worker/controller fanout 상황에서의 PostgreSQL connection exhaustion
- `RISK-0057` claim / renewal 부하에서의 Postgres write lock contention
- `RISK-0059` audit 부하에서의 JSONB-heavy ledger write 비용
- `RISK-0060` control-plane churn 상황에서의 WAL / storage pressure
- `RISK-0061` controller throughput / SPOF pressure

## 이번 단계의 목적

- claim / renew / audit write path를 더 가볍게 만듭니다
- JSONB-heavy audit churn을 줄일 수 있는 구조적 여지를 만듭니다
- controller-mediated DB boundary는 유지하면서 throughput envelope를 더 분명히 봅니다
- 오래된 audit/log retention 기준을 운영 정책으로 처음 고정합니다
- Postgres churn 축소 조치가 실제 contention/latency 개선에 도움이 되는지 검증합니다

## 구현 범위

- heartbeat / renew write coalescing 추가 보강
- audit/event write path 중 high-frequency 경로 식별 및 경량화
- retention / archival policy 초안과 운영 표면 추가
- controller throughput 진단 표면 보강
- Step 22 contention smoke를 churn/latency 비교까지 확장
- Postgres 운영 경계와 retention 정책을 ADR / note / runbook에 반영

## 이번 단계에서 하지 않는 것

- Redis queue / pubsub / cache 도입
- external side-effect runtime 개방
- GUI / dashboard / SCM integration
- Postgres 위의 LangGraph state persistence

## Acceptance Criteria

- high-frequency lease / audit path가 이전보다 더 적은 write churn으로 동작한다
- founder/operator가 connection pressure와 controller pressure를 더 구분해서 읽을 수 있다
- audit retention 기준이 코드/문서 양쪽에 고정된다
- `RISK-0059`, `RISK-0060`, `RISK-0061`이 적어도 mitigating 이상으로 줄어든다
- `RISK-0055`, `RISK-0057`은 Step 23 기준으로 추가 완화되거나 일부 closure 근거가 생긴다

## 리스크 연결

- 직접 타깃:
  - `RISK-0059`
  - `RISK-0060`
  - `RISK-0061`
- 직접 완화:
  - `RISK-0055`
  - `RISK-0057`
- 이번 단계에서 직접 다루지 않는 것:
  - `RISK-0051`
  - `RISK-0036`
  - `RISK-0006`
  - `RISK-0026`
  - `RISK-0045`
