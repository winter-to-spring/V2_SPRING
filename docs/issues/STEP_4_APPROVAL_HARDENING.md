# [코어] Step 4 - Approval hardening (reject reason + pending write barrier)

## 배경 / 문제

Step 3에서 approval list / resolve CLI까지는 만들었지만, human-in-the-loop를
진짜 운영 경계로 보려면 두 가지가 더 필요합니다.

- 반려 사유가 남아야 합니다.
- approval 대기 중에는 non-approval write가 막혀야 합니다.

지금 이 둘이 없으면 approval은 존재하지만, 다음 planner loop에 학습을
남기지 못하고, pending 상태에서도 run이 계속 변할 수 있습니다.

## 이번 단계의 목적

1. rejection feedback를 구조화된 상태와 ledger에 남깁니다.
2. pending approval 동안 non-approval write를 service layer에서 막습니다.
3. 다음 planner/replanner 단계로 넘어가기 전에 approval semantics를 더
   단단하게 만듭니다.

## 구현 범위

- `approval resolve --reject --reason "..."`
- optional approval resolution reason persistence
- approval resolution ledger payload 강화
- service-level pending approval write barrier
- barrier 검증 테스트
- risk register와 implementation note 갱신

## 이번 단계에서 하지 않는 것

- approval timeout / expiry
- suspended 상태
- DB-level or distributed lock
- background worker watchdog

## Acceptance Criteria

- rejection without `--reason` is refused
- rejection reason is visible in approval state and ledger events
- pending approval blocks new non-approval writes
- approval resolution remains allowed while pending
- tests and CLI proof both pass
