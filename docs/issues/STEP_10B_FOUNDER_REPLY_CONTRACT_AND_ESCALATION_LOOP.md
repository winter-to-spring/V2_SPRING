# [코어] Step 10-b - Founder reply contract and hint-first escalation loop

## 배경 / 문제

Step 10-a에서 planner는 이제 합법적으로 `EscalationProposal`을 제출할 수
있습니다. 하지만 founder가 그 escalation에 어떤 형식으로 답하는지,
그 답이 planner에게 어떻게 되먹이는지는 아직 계약이 없습니다.

이 단계가 없으면:
- founder reply가 단순 텍스트 힌트인지 강제 override인지 모호해지고
- planner가 escalation만 반복하는 thrash가 생기고
- human-in-the-loop semantics가 다시 자연어 감에 의존하게 됩니다

## 이번 단계의 목적

1. founder reply를 typed / replayable contract로 고정합니다.
2. **hint-first / override-available** 정책을 실제 상태 전이와 연결합니다.
3. escalation 이후 planner 재진입 루프를 bounded하게 만듭니다.
4. founder reply ambiguity와 premature escalation 리스크를 줄입니다.

## 구현 범위

- founder reply typed model
- reply kind 구분
  - `hint`
  - `override`
  - `reject`
- hint payload와 override payload를 분리한 union contract
- escalation replay linkage
- repeated escalation throttle or cooldown 1차 정책
- planner 재진입 시 founder hint를 bounded context에 주입하는 경로
- CLI proof path for founder replies
- 관련 ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- production provider hardening
- background worker 자동 루프
- semantic duplicate 고도화 전체
- founder UI

## 리스크 게이트

- `RISK-0016` premature escalation thrash
- `RISK-0017` founder reply contract ambiguity

추가로 주의할 점:
- planner가 어려운 상황에서 너무 쉽게 escalation으로 도망가지 않도록
  escalation policy를 prompt와 시스템 계약 양쪽에서 제한해야 합니다
- founder hint는 단순 텍스트가 아니라 가능한 한
  `help_kind + requested_help + reply_kind` 형태로 구조화되어야 합니다

## Acceptance Criteria

- founder reply가 typed / replayable하다
- hint와 override가 명확히 구분된다
- escalation 이후 재진입 경로가 deterministic하다
- planner는 founder hint를 bounded stateful context의 일부로 받는다
- repeated escalation에 대한 cooldown 또는 throttle이 존재한다
- CLI에서 founder reply와 이후 planner 재진입을 proof할 수 있다

## 메모

- 기본 경로는 **hint-first**입니다
- override는 가능하지만 예외 경로로 제한합니다
- planner가 모를 때 아무 action이나 찍지 않고 escalation할 수 있어야 하지만,
  `blocking_reason`, `requested_help`, `analysis_summary` 없이 도망가서는 안 됩니다
