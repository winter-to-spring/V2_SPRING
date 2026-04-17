# ADR-0003: 핵심 상태 모델

## 상태

Accepted

## 배경

이전 시스템은 동작과 상태가 쉽게 분리되었습니다. source of truth가 충분히
명시적이지 않았기 때문에 replay와 verification도 약했습니다.

## 결정

영속적인 system of record는 아래 엔티티를 중심으로 구성됩니다.

- Project
- Run
- Module
- Task
- Capability
- Decision
- Artifact
- Approval
- Budget
- Risk
- Observation

Step 1은 `Run`을 느슨한 dictionary payload가 아니라 typed되고 validated된
모델로 구현하는 것부터 시작합니다.

Step 2는 같은 접근을 `Decision`과 `Observation`으로 확장하며, 이들도
ad-hoc log blob이 아니라 typed record로 저장합니다.

## 결과

- 자연어 summary는 authoritative하지 않습니다.
- Planner와 UI는 상태를 발명하지 않고 ledger로부터 파생되어야 합니다.
- schema discipline이 최상위 설계 관심사가 됩니다.
