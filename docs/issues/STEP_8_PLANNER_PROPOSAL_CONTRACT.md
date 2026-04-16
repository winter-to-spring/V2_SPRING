# [코어] Step 8 - Planner proposal contract + legal action selection guard + CLI proof

## 배경 / 문제

Step 7까지 오면서 V2_SPRING은 이제 founder가 CLI에서 다음을 직접 확인할 수 있게 됐습니다.

- 현재 run의 compact snapshot
- 현재 상태에서 가능한 deterministic legal moves
- approval / rejection / bounded execution 이후의 분기 상태

하지만 아직 중요한 한 조각이 비어 있습니다.

우리는 아직 **planner가 어떤 형식으로 선택을 제출해야 하는지**, 그리고 **그 선택이 정말 현재 legal move 집합 안에 있는지**를 검증하는 공식 계약을 갖고 있지 않습니다.

지금 LangGraph를 바로 붙이면 위험합니다.

- 잘못된 action을 고를 수 있음
- stale snapshot을 바탕으로 옛 상태에 반응할 수 있음
- planner rationale이 남지 않으면 왜 그런 선택을 했는지 설명할 수 없음
- planner가 고른 액션과 executor가 실제 허용하는 액션이 어긋날 수 있음

그래서 Step 8에서는 실제 LLM 호출보다 먼저, **planner가 들어오기 직전의 input/output contract와 legal action guard**를 고정해야 합니다.

즉 이번 단계는 “planner를 붙인다”가 아니라, **planner가 끼어들 수 있는 안전한 슬롯(slot)을 만든다**는 의미입니다.

---

## 이번 단계의 목적

1. planner proposal의 typed contract를 정의합니다.
2. proposal이 현재 snapshot / possible actions와 일치하는지 deterministic하게 검증합니다.
3. founder가 CLI에서 planner proposal을 직접 넣고, legal / illegal 여부를 검증할 수 있게 합니다.
4. planner 판단의 근거와 기대 결과를 `Decision`으로 남길 수 있게 합니다.
5. 이후 LangGraph adapter가 이 계약만 만족하면 붙을 수 있게 준비합니다.

---

## 구현 범위

이번 단계에서는 아래 범위까지만 포함합니다.

- typed `PlannerProposal` model 도입
- proposal validation 규칙 정의
  - snapshot hash 일치 여부
  - selected action이 legal move 집합 안에 있는지
- planner proposal을 Decision으로 저장하는 경로 추가
- CLI proof surface 추가
  - 예: `v2-spring planner propose <run-id> --action ... --rationale ...`
  - 예: `v2-spring planner show <run-id>` 또는 동등한 조회
- illegal proposal을 explicit error로 거부
- 관련 테스트 추가
- ADR / 설계 문서 / implementation note 반영

---

## 이번 단계에서 하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- 실제 LangGraph 연동
- 실제 LLM 호출
- automatic execution chaining
- multi-step replanning loop 전체
- UI
- CrewAI workforce 연결
- background worker
- distributed locking

즉 이번 단계는 **planner contract를 증명하는 최소 CLI loop**에만 집중합니다.

---

## 구체 작업 항목

- [ ] `PlannerProposal` typed model 정의
- [ ] proposal validation 규칙 정의
- [ ] snapshot hash 기반 freshness check 정책 정의
- [ ] selected action legal move validation 구현
- [ ] proposal -> Decision 저장 경로 구현
- [ ] `planner propose` CLI 추가
- [ ] `planner show` 또는 동등한 조회 CLI 추가
- [ ] illegal proposal explicit error 처리
- [ ] accepted proposal pretty/json 출력 정리
- [ ] 관련 테스트 추가
- [ ] ADR 작성 또는 갱신
- [ ] implementation note 작성

---

## Acceptance Criteria

- planner proposal은 dict가 아니라 typed/validated model로 들어옵니다.
- proposal은 snapshot hash와 selected action을 명시해야 합니다.
- selected action이 현재 legal move 집합 밖이면 명시적 에러로 거부됩니다.
- snapshot hash가 현재 상태와 맞지 않으면 stale proposal로 거부되거나 명확히 표시됩니다.
- legal proposal은 Decision으로 저장됩니다.
- founder가 CLI로 planner proposal을 직접 검증할 수 있습니다.
- illegal proposal과 legal proposal이 CLI에서 분명히 구분됩니다.
- 테스트가 통과합니다.
- 문서와 실제 구현이 일치합니다.

---

## 리스크 / 메모

- proposal validation과 possible-actions 엔진 로직이 서로 어긋나면 planner contract의 신뢰도가 무너질 수 있습니다.
- stale snapshot 정책을 너무 엄격하게 잡으면 UX가 거칠어지고, 너무 느슨하게 잡으면 planner가 거짓 계기판을 읽게 됩니다.
- proposal을 너무 자유롭게 만들면 Step 7에서 고정한 deterministic 경계를 다시 흐릴 수 있습니다.
- 이번 단계에서는 action ranking이나 best-choice 판단이 아니라, **proposal legality와 traceability**에 집중해야 합니다.

---

## 연결 문서 / ADR

- `docs/specs/TRACER_BULLET.md`
- `docs/implementation-notes/STEP_7_RUN_SNAPSHOT_POSSIBLE_ACTIONS.md`
- `docs/adr/0003-core-state-model.md`
- `docs/adr/0004-deterministic-substrate.md`

이번 단계가 끝나면 다음으로는 LangGraph adapter 또는 bounded replanning loop를 더 자연스럽게 올릴 수 있어야 합니다.
