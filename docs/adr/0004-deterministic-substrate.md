# ADR-0004: 결정론적 Substrate

## 상태

Accepted

## 배경

상태 변경이 비결정론적이거나 replay 불가능하다면 자율 planning은 신뢰할 수
없습니다.

## 결정

- Postgres는 durable record store가 됩니다.
- Redis는 coordination 전용입니다.
- planner는 상태를 직접 변경하지 않습니다.
- deterministic executor가 상태 전이를 수행합니다.
- `evaluate_possible_actions()` 같은 deterministic read-side engine은 순수하고
  side-effect가 없어야 합니다.
- V2는 hybrid persistence model로 시작합니다.
  - 현재 진실을 담는 state table
  - replay와 audit을 위한 append-only event ledger
- Decision과 Observation은 typed table에 기록되고, immutable process
  evidence로서 append-only ledger에도 미러링됩니다.

## 결과

- queue, lease, cancel, retry, resume semantics는 명시적이어야 합니다.
- reconciliation과 replay는 필수입니다.
- planner / executor 계약은 좁고 테스트 가능해야 합니다.
