# [코어] Step 10 - LangGraph planner adapter with bounded stateful context

## 배경 / 문제

Step 9까지 오면서 planner slot은 bounded하게 운영할 수 있게 됐지만,
아직 실제 planner adapter는 붙지 않았습니다.

Step 10은 단순한 LLM 연결이 아니라, **LangGraph planner adapter가 어떤
형태의 입력을 받고 어떤 형태의 출력을 내야 하는지**를 실제 코드로
증명하는 단계입니다.

이번 단계에서 가장 중요한 결정은 세 가지입니다.

1. planner는 stateless가 아니라 **bounded stateful**
2. raw ledger 전체를 넣지 않고 **Structured Failure Report** 사용
3. output은 단일 action 강제가 아니라
   **`ActionProposal | EscalationProposal` discriminated union**

## 이번 단계의 목적

1. LangGraph planner adapter의 첫 bounded proof path를 만든다
2. structured failure report 기반 context window를 만든다
3. legal action과 escalation을 서로 다른 타입으로 다룬다
4. malformed output / stale churn / planner loop drift를 bounded하게 제어한다

## 구현 범위

- `PlannerContextWindow` typed model
- `StructuredFailureReport` typed model
- `ActionProposal | EscalationProposal` discriminated union
- LangGraph adapter skeleton
- scripted transport 기반 CLI proof
- stale quota fairness
- planner escalation recording
- adapter format failure recording
- ADR / implementation note / risk register 갱신

## Step 10 output contract decisions

- planner는 `stateless function`이 아니라 **bounded stateful planner**로 간다
- raw ledger 전체를 planner 입력에 직접 주지 않는다
- planner 입력은 **Structured Failure Report**와 최근 bounded context만 사용한다
- output은 자유 텍스트가 아니라 **structured output**을 기본 경로로 사용한다
- output contract는 단일 action 강제가 아니라
  **`ActionProposal | EscalationProposal` discriminated union**으로 간다
- `analysis_summary`와 `confidence`는 필수 reasoning metadata로 남긴다
- founder interaction은 **hint-first / override-available** 정책으로 설계하고,
  이번 단계에서는 hint-first 쪽만 formalize한다

## 선행 리스크 게이트

- `RISK-0013` execution failure feedback loop
- `RISK-0014` stale fairness / separate stale quota
- `RISK-0015` structured failure report fidelity
- `RISK-0016` premature escalation / escalation thrash
- `RISK-0017` founder reply contract ambiguity

## 이번 단계에서 하지 않는 것

- founder override execution
- full autonomous loop
- background worker
- semantic duplicate 고도화
- production transport hardening 전체

## Acceptance Criteria

- planner adapter는 bounded context window를 입력으로 받는다
- output은 discriminated union으로 파싱된다
- `ActionProposal`은 기존 legal guard를 통과한다
- `EscalationProposal`은 founder-facing governance observation으로 기록된다
- stale는 separate stale quota로 관리된다
- malformed output은 explicit format failure로 기록된다
- CLI에서 `planner invoke`로 proof 가능하다

## 리스크 / 메모

- failure report 품질이 낮으면 planner 품질도 같이 낮아진다
- escalation은 아직 hint-first만 formalize했고 override는 후속 단계다
- exact semantic duplicate 방지는 아직 future hardening 영역이다

## 연결 문서 / ADR

- `docs/adr/0006-bounded-replanning-governance.md`
- `docs/adr/0007-planner-decision-output-contract.md`
- `docs/implementation-notes/STEP_10_LANGGRAPH_PLANNER_ADAPTER.md`
