# Risk ID: RISK-0059
Title: JSONB-heavy ledger write가 audit 부하 아래에서 Postgres write 비용을 키울 수 있음
Class: Before Scale
Status: Open
Owner: Storage / Audit ledger
Observed In: Step 22 contention-soak planning

## 설명

V2_SPRING은 ledger와 replay path 일부에 유연한 JSON payload를 사용합니다.
이 유연성은 유용하지만, write volume이 커지면 비용도 커질 수 있습니다.

JSONB payload가 넓은 index를 많이 달거나 hot path에서 너무 자주 다시
써지기 시작하면, lock contention이 주된 병목이 되기 전부터 write 비용이
상승합니다.

## 영향

- heartbeat/audit write latency가 서서히 증가할 수 있음
- disk I/O와 index maintenance가 throughput을 깎아먹을 수 있음
- Postgres는 논리적으로는 맞아도 운영적으로 둔해질 수 있음

## 왜 중요한가

Step 22는 contention과 controller trust boundary에 집중하지만, scale이 커질수록
드러날 storage 비용 증가를 가려서는 안 됩니다.

## 권장 완화책

- 자주 조회하지 않는 JSONB 필드에는 index를 달지 않는다
- 가능하면 hot-path write table을 lean하게 유지한다
- lock order뿐 아니라 audit JSON payload 자체가 latency를 만드는지 측정한다
- 증거가 쌓이면 초고빈도 운영 write와 richer replay payload를 분리한다

## Capability Gate
- Capability: higher-volume audit/event traffic on Postgres
- Gate mode: Before Scale
- Blocked until: JSONB write overhead is understood and bounded under expected event load

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR:
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## 종료 기준

- 현실적인 audit volume 아래에서 JSONB write 비용이 측정된다
- hot-path table이 불필요한 index/update penalty를 지불하지 않는다

## Last Updated
- 2026-04-17
