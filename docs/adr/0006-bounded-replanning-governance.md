# ADR 0006: Bounded Replanning Loop와 Planner Attempt 거버넌스

## 배경

Step 8은 typed planner proposal contract와 legal-action guard를 도입했지만,
반복되는 planner failure를 어떻게 다룰지는 의도적으로 미뤄두었습니다.

실제 LangGraph adapter나 자동 replanning loop를 붙이기 전에, 시스템은 아래 네
질문에 결정론적으로 답할 수 있어야 합니다.

1. 하나의 state segment 안에서 planner 실수는 몇 번까지 허용되는가?
2. 어떤 failure가 planner retry budget을 소모하는가?
3. duplicate submission은 어떻게 처리되는가?
4. exhausted된 planner phase를 founder가 어떻게 다시 열 수 있는가?

이 답이 없으면, future planner는 stale hash, illegal action, repeated proposal로
무한 루프를 돌며 token을 태우고 ledger를 어지럽힐 수 있습니다.

## 결정

V2_SPRING은 **phase-scoped planner budget**과 append-only planner-attempt
ledger를 사용합니다.

- planner retry는 run 전체 기준이 아니라 **phase** 기준으로 bounded합니다.
- phase는 결정론적인 `planner_phase_key`로 식별합니다.
- phase key는 의미 있는 advancement signal만으로 계산됩니다.
  - run status
  - pending approval state
  - latest rejection reason
  - task summary
  - latest task headline
  - latest artifact headline
- 아래와 같은 planner-only trace는 phase를 전진시키면 안 됩니다.
  - accepted planner decision
  - planner escalation record
  - founder-help lane marker
  - founder hint / reject / override bookkeeping
  - manual recharge record
- 예:
  - approval 해소나 bounded task completion은 phase를 전진시킬 수 있음
  - founder escalation을 열거나 닫는 것만으로는 phase가 전진하면 안 됨

## Attempt Budget 정책

- 초기 planner phase budget은 `3`입니다.
- 아래 outcome은 budget을 소모합니다.
  - `rejected_stale`
  - `rejected_illegal`
  - `rejected_duplicate_cognitive`
- 아래 outcome은 budget을 소모하지 않습니다.
  - `accepted`
  - `rejected_duplicate_transport`
  - `manual_recharge`
  - planner proposal 경로 바깥의 execution-time failure
- phase budget이 고갈되면 시스템은 `phase_exhausted` planner attempt를 기록하고,
  founder가 명시적으로 recharge하기 전까지 추가 planner proposal을 막습니다.

## Duplicate 정책

Planner duplicate는 두 층으로 처리합니다.

### Transport-level duplicate

- 정의: 현재 active planner phase 안에서 같은 `submission_key`가 다시 제출된 경우
- 결과: `rejected_duplicate_transport`로 명시적 거부
- budget 영향: budget을 소모하지 않음

### Cognitive duplicate

- 정의:
  - 현재 active planner phase 안에서 같은 proposal fingerprint가 반복되거나
  - 같은 action에 대해 정규화된 proposal intent signature가 반복되거나
  - 같은 active planner phase 안에서 이미 하나의 proposal이 accepted되었는데도
    상태가 전진하지 않은 상태에서 또 proposal이 들어온 경우

## 결과

- planner retry는 phase 단위로 bounded되고 replay 가능해집니다.
- duplicate semantics가 transport-level과 cognitive level로 분리됩니다.
- founder는 exhausted된 phase를 명시적으로 recharge할 수 있습니다.
- planner governance가 단순한 "retry count"가 아니라 phase-aware 운영 규칙으로
  고정됩니다.
