# [코어] Step 7 - RunSnapshot typed view + deterministic possible-actions engine + CLI inspection surface

## 배경 / 문제

Step 6까지 오면서 founder는 CLI에서 다음을 직접 검증할 수 있게 됐습니다.

- run이 생성되는지
- approval이 실제로 걸리고 해제되는지
- bounded task 1개가 실제로 수행되는지
- artifact가 provenance와 hash를 포함해 남는지
- replay로 실행 서사를 다시 따라갈 수 있는지

그런데 V2_SPRING이 진짜 자율형으로 넘어가려면, 이제는 사람이 매번 상태를 해석하는 대신 시스템이 **“현재 이 run이 무엇을 할 수 있는지”**를 구조화해서 보여줘야 합니다.

지금 필요한 것은 LLM을 붙이는 게 아니라, 그 직전에 놓일 **typed `RunSnapshot`과 deterministic `possible actions` 엔진**입니다.

즉 이번 단계는 자율 판단 자체가 아니라, **자율 판단 직전의 관측면과 액션 후보화**를 만드는 단계입니다.

---

## 이번 단계의 목적

1. `RunSnapshot` typed view를 도입합니다.
2. 현재 run 상태를 바탕으로 가능한 다음 액션을 deterministic하게 계산합니다.
3. founder가 CLI에서 현재 상태와 가능한 다음 행동을 직접 확인할 수 있게 합니다.
4. 이후 planner/replanner가 읽을 입력 계약을 준비합니다.
5. planner와 executor의 경계를 계속 분명하게 유지합니다.

---

## 구현 범위

이번 단계에서는 아래 범위까지만 포함합니다.

- `RunSnapshot` typed / validated model 도입
- snapshot 생성 규칙 정의
- deterministic `possible-actions` engine 도입
- CLI inspection surface 추가
  - `v2-spring run snapshot <run-id>`
  - `v2-spring run actions <run-id>`
- 사람 친화적인 pretty 출력
- JSON 출력 분리
- 관련 테스트 추가
- ADR / 설계 문서 / implementation note 반영

---

## 이번 단계에서 하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- LangGraph planner 통합
- CrewAI execution workforce 통합
- 실제 LLM 호출
- full replanning loop
- UI
- multi-task orchestration 확장
- budget policy 전체
- hiring workflow 전체
- Redis coordination 확장

즉 이번 단계는 **planner가 들어오기 직전의 deterministic substrate 확장**에만 집중합니다.

---

## 구체 작업 항목

- [ ] `RunSnapshot` typed model 정의
- [ ] snapshot 생성 규칙 정의
- [ ] snapshot validation 강제
- [ ] `snapshot_timestamp`와 `state_hash` 포함
- [ ] deterministic `possible actions` enum / model 정의
- [ ] approval 대기 / rejection / completed / failed 상태별 액션 정책 정의
- [ ] `run snapshot` CLI 추가
- [ ] `run actions` CLI 추가
- [ ] pretty 출력 추가
- [ ] JSON 출력 제공
- [ ] snapshot / actions 테스트 추가
- [ ] invalid state / empty action case 테스트 추가
- [ ] ADR 작성 또는 갱신
- [ ] implementation note 작성

---

## Acceptance Criteria

- `RunSnapshot`은 dict가 아니라 typed/validated model로 생성됩니다.
- `RunSnapshot`은 `snapshot_timestamp`와 `state_hash`를 포함합니다.
- 현재 run 상태를 기반으로 가능한 액션 목록이 deterministic하게 계산됩니다.
- founder가 CLI로 run snapshot을 확인할 수 있습니다.
- founder가 CLI로 현재 run이 어떤 다음 행동을 할 수 있는지 확인할 수 있습니다.
- invalid state는 validation error로 잡힙니다.
- snapshot과 action 결과가 ledger / state와 일관됩니다.
- approval 대기, rejection, completed, failed 상태에서 액션 후보가 의도대로 제한됩니다.
- JSON 출력이 이후 planner adapter에서 읽기 쉬운 구조를 유지합니다.
- 테스트가 통과합니다.
- 문서와 실제 구현이 일치합니다.

---

## 리스크 / 메모

- snapshot이 너무 비대해지면 planner context와 founder 가독성이 동시에 나빠질 수 있습니다.
- `possible actions`는 deterministic legal moves만 나열해야 하며, planner judgment를 섞으면 Step 8 이후가 흐려집니다.
- pending approval이 있는데 다른 mutating action이 보이면 human-in-loop 경계가 무너집니다.
- 고동시성 환경에서 snapshot staleness를 완전히 없애는 것은 이번 단계 범위를 넘기므로 risk register로 관리합니다.
- read-model 비용 최적화는 현재 규모에선 fixed-query로 충분하지만, 장기적으로는 별도 projection/materialized view가 필요할 수 있습니다.

---

## 연결 문서 / ADR

- `docs/architecture/EXECUTION_PLAN.md`
- `docs/specs/TRACER_BULLET.md`
- `docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md`
- `docs/adr/0003-core-state-model.md`
- `docs/adr/0004-deterministic-substrate.md`
- `docs/adr/0005-founder-verification-surface.md`

이번 단계가 끝나면 다음으로는 planner output schema 또는 bounded replanning loop 쪽으로 더 자연스럽게 이어갈 수 있어야 합니다.
