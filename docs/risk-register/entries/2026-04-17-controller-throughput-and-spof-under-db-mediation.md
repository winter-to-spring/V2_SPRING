# Risk ID: RISK-0061
Title: controller-mediated DB access가 throughput 병목이나 SPOF가 될 수 있음
Class: Before Next Phase
Status: Mitigating
Owner: Control plane / Runtime coordination
Observed In: Step 22 controller-boundary hardening

## 설명

controller-mediated DB access는 V2_SPRING에 맞는 trust boundary지만, 병목의
형태를 다른 방향으로 바꿉니다.

모든 worker, reconcile path, 운영 query가 controller를 통과해야 한다면,
controller 자체가 시스템의 좁은 허리가 될 수 있습니다.

## 영향

- Postgres가 건강해도 request backlog가 쌓일 수 있음
- founder/operator UX가 DB가 아니라 controller 때문에 느려질 수 있음
- 시스템이 DB 안전성과 맞바꿔 새로운 application-layer 병목을 만들 수 있음

## 왜 중요한가

controller boundary는 전략적으로 맞지만, Step 22는 이 경계를 마법처럼
숨기는 대신 관측 가능하고 의도적으로 가벼운 것으로 만들어야 합니다.

## 권장 완화책

- controller DB mediation path를 좁고 목적 지향적으로 유지한다
- 장애가 DB 측인지 controller 측인지 드러낸다
- worker의 direct DB access를 막으면서 controller throughput을 별도로 측정한다
- 더 넓은 cache/queue layer는 필요하다는 증거가 생길 때까지 미룬다

현재 완화 상태:

- Step 22는 `v2-spring doctor`에서 controller DB boundary를 명시적으로 보여준다
- 같은 doctor surface가 lock waiting / pool pressure와 application boundary를 구분해 보여준다
- live contention smoke는 controller boundary에 대해 가정이 아닌 측정 가능한 신호를 준다

## Capability Gate
- Capability: higher-fanout execution traffic through a controller-owned DB boundary
- Gate mode: Before Next Phase
- Blocked until: controller throughput and failure modes are observable under contention smoke

## Issue Link
- GitHub Issue: #49

## Doc Links
- ADR: ../../adr/0020-postgres-contention-soak-and-controller-boundary.md
- Design note: ../../issues/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md
- Design note: ../../implementation-notes/STEP_22_POSTGRES_CONTENTION_AND_CONTROLLER_DB_BOUNDARY.md

## 종료 기준

- controller-only DB mediation이 측정 가능한 throughput envelope를 가진다
- operator surface가 controller pressure와 DB pressure를 구분할 수 있다

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating with Step 22 controller-boundary diagnostics)
