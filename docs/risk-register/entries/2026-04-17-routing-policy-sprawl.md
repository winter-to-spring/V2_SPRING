# Risk ID: RISK-0026
Title: 명시적 dispatcher 규칙이 runtime 증가와 함께 감사하기 어려운 routing blob으로 커질 수 있음
Class: Later Hardening
Status: Open
Owner: Execution plane / Dispatcher
Observed In: Step 12-a routing policy planning

## 설명

Step 12-a는 opaque scoring registry 대신 명시적인 rule branch와 named
guard function으로 시작하도록 의도적으로 설계되었습니다.

이 선택은 초기 통제와 auditability 측면에서는 맞지만, execution runtime과
requirement 차원이 늘어날수록 규칙이 커져 reasoning하기 어려운 거대한
routing blob이 될 수 있습니다.

## 영향

- routing 동작을 감사하거나 안전하게 변경하기 어려워짐
- 새로운 runtime을 추가할 때 너무 많은 조건을 건드려야 할 수 있음
- policy conflict를 코드 리뷰에서 발견하기 더 어려워짐

## 왜 중요한가

dispatcher는 점점 control plane에서 가장 민감한 경계 중 하나가 되고 있습니다.

규칙 집합이 커지고 암묵적으로 변하면, 미래의 execution-plane 변경이 안전성
문제나 비용 누수를 다시 열어버릴 수 있습니다.

## 권장 완화책

- Step 12-a에서는 명시적 rule branch로 시작한다
- routing policy를 작은 named guard function과 compact policy table로 유지한다
- 모든 routing branch마다 좁은 테스트를 추가한다
- 안정적인 runtime matrix가 생긴 뒤에야 scoring/registry 일반화를 검토한다

## Capability Gate
- Capability: expanding execution runtimes beyond the initial Step 12 proof
- Gate mode: Later Hardening
- Blocked until: routing rules remain auditable as new runtimes are added

## Issue Link
- GitHub Issue: #28

## Doc Links
- ADR: docs/adr/0010-execution-plane-routing-policy.md
- Design note: docs/implementation-notes/STEP_12A_EXECUTION_PLANE_ROUTING_POLICY.md

## 종료 기준

- runtime coverage가 늘어나도 routing rule이 compact하고 테스트 가능하게 유지된다
- auditability를 약화시키지 않는 미래 일반화 경로가 존재한다

## Last Updated
- 2026-04-17
