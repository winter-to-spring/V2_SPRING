# ADR-0002: Human-In-The-Loop 경계

## 상태

Accepted

## 배경

거버넌스 없는 자율성은 검토되지 않은 agent 채용, 비용 증가, 위험한 변경의
즉시 실행으로 이어집니다.

## 결정

아래 항목에는 사람 승인이 반드시 필요합니다.

- agent hiring
- budget 증가
- destructive change
- scope expansion
- governance가 고위험으로 태깅한 모든 action

## 결과

- Approval은 1급 도메인 엔티티가 됩니다.
- Planner output은 escalation과 pause 상태를 지원해야 합니다.
- 완전 자율 모드는 의도적으로 첫 운영 모드가 아닙니다.
- tracer bullet은 rich UI를 시도하기 전에 CLI를 통해 approval 생성과
  approval 해소를 드러내야 합니다.
- approval rejection은 structured feedback을 지원해야 하며, 그래야 replanning이
  같은 제안을 반복하는 대신 사람의 지침을 학습할 수 있습니다.
- approval-gated run은 더 강한 동시성 제어가 붙기 전에도 gate가 풀릴 때까지
  non-approval write를 거부해야 합니다.
- approval barrier는 명시적으로 실패해야 합니다. 호출자는 쓰기가 governance에
  의해 막힌 것인지, 실제로 받아들여진 것인지 알아야 하므로 silent drop은
  금지합니다.
- approval gate는 무한 pause가 아니라 bounded pause입니다. 각 approval은
  `expires_at`을 기록하고, 명시적 timeout sweep이 overdue gate를 `expired`로
  처리해 run을 `suspended`로 옮길 수 있어야 합니다.
- approval pending 동안에도 passive audit observation은 기록할 수 있지만,
  상태를 전진시키거나 planner를 다시 움직이는 follow-up work가 되어서는 안 됩니다.
