# [코어] Step 3 - Approval typed model + EventLedger 연동 + approval list/resolve CLI

## 배경 / 문제

Step 2까지 오면서 founder는 CLI에서 다음을 직접 확인할 수 있게 됐습니다.

- run이 생성되었는지
- 어떤 초기 observation이 기록되었는지
- 어떤 초기 decision이 기록되었는지
- 이 과정이 append-only ledger에 남았는지

하지만 아직 중요한 반자동 구조 하나가 비어 있습니다.

바로 **human-in-the-loop 승인 루프**입니다.

V2_SPRING은 완전자율 시스템이 아니라, 중요한 경계에서는 사람이 승인하거나 반려할 수 있어야 하는 반자동 조직 운영체계입니다. 지금 단계에서는 founder가 CLI만으로도 아래를 직접 확인하고 제어할 수 있어야 합니다.

- 어떤 approval이 pending인지
- 왜 approval이 필요한지
- approve / reject를 하면 무슨 일이 일어나는지
- 그 판단이 append-only ledger에 어떻게 남는지

## 이번 단계의 목적

- `Approval` 최소 typed model을 도입합니다.
- approval lifecycle을 append-only `EventLedger`와 연결합니다.
- `v2-spring approval list`와 `v2-spring approval resolve` CLI를 추가합니다.
- founder가 UI 없이도 human-in-the-loop를 직접 검증할 수 있게 합니다.

## 구현 범위

이번 단계에서는 아래만 포함합니다.

- `Approval` 최소 typed model
- `ApprovalStatus` 등 필요한 Enum 및 validation
- append-only ledger와 approval 이벤트 연동
- 최소 approval seed / bootstrap 흐름
- CLI
  - `v2-spring approval list`
  - `v2-spring approval resolve <approval-id> --approve`
  - `v2-spring approval resolve <approval-id> --reject`
- 관련 테스트 추가
- ADR / 설계 문서 / implementation note 반영

## 구현하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- approval UI
- budget policy 전체
- hiring request 전체
- task execution 전체
- artifact registry 전체
- full replay 구현
- CrewAI / LangGraph 통합
- Redis coordination
- queue / lease / retry semantics 전체

## 구체 작업 항목 체크리스트

- [ ] `Approval` 최소 typed model 정의
- [ ] `ApprovalStatus` / 관련 Enum 정의
- [ ] validation 규칙 추가
- [ ] approval state table과 ledger event 연결
- [ ] 최소 approval 생성 흐름 정의
- [ ] `approval list` CLI 구현
- [ ] `approval resolve --approve` CLI 구현
- [ ] `approval resolve --reject` CLI 구현
- [ ] approval resolve 시 상태 전이와 ledger 기록 연결
- [ ] invalid transition 테스트 추가
- [ ] list / resolve CLI 출력 테스트 추가
- [ ] ADR 작성 또는 갱신
- [ ] implementation note 작성
- [ ] tracer bullet 문서에 approval 검증 흐름 반영

## Acceptance Criteria

- `Approval`이 typed/validated model로 저장됩니다.
- pending approval이 CLI에서 조회됩니다.
- founder가 CLI에서 approve / reject를 직접 실행할 수 있습니다.
- approval 상태 전이가 ledger에 append-only로 기록됩니다.
- invalid transition은 명확한 에러로 거절됩니다.
- 테스트가 통과합니다.
- 문서와 실제 구현이 일치합니다.

## 리스크 / 메모

- approval을 너무 일반화하면 Step 3가 무거워질 수 있습니다.
- Step 3의 핵심은 “승인 개념 전체를 완성”이 아니라 “승인 루프를 CLI로 검증 가능하게 만드는 것”입니다.
- 승인 결과가 state table에는 반영되는데 ledger에는 안 남는 식의 비대칭은 절대 허용하면 안 됩니다.
- approval reason / consequence 포맷은 사람이 읽을 수 있어야 하므로 raw blob보다 설명 가능한 구조를 우선합니다.

## 연결 문서 / ADR

- `docs/architecture/EXECUTION_PLAN.md`
- `docs/specs/TRACER_BULLET.md`
- `docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md`
- `docs/adr/0002-human-in-the-loop-boundaries.md`
- `docs/adr/0004-deterministic-substrate.md`

이번 단계가 끝나면 다음으로
- `run replay`
- bounded task execution
- planner 가능한 action selection
순으로 이어갈 수 있어야 합니다.
