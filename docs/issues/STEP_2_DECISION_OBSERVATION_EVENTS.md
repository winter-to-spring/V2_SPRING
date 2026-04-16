# [코어] Step 2 - Decision/Observation typed model + EventLedger 연동 + run events CLI

## 배경 / 문제

Step 1에서 `Run` 생성과 조회가 CLI로 검증 가능해졌지만, 아직 founder가 "이 run에서 실제로 어떤 판단이 있었고, 무엇을 관측했는지"를 CLI만으로 충분히 확인할 수는 없습니다.

V2_SPRING의 다음 조각은 **더 깊은 검증 가능성**이어야 합니다.
즉, 단순히 run이 생성되는 수준을 넘어서:

- 어떤 결정을 했는지
- 어떤 관측이 들어왔는지
- 그 판단과 관측이 append-only ledger에 어떻게 남는지

를 CLI에서 바로 볼 수 있어야 합니다.

## 이번 단계의 목적

- `Decision`과 `Observation`의 최소 typed model을 도입합니다.
- 두 모델을 append-only `EventLedger`와 연결합니다.
- `v2-spring run events <run-id>` CLI로 run의 사건 흐름을 사람이 확인할 수 있게 합니다.
- Step 1의 `run create / show`를 확장해, founder가 CLI만으로 더 깊게 검증할 수 있는 slice를 만듭니다.

## 구현 범위

이번 단계에서는 아래만 포함합니다.

- `Decision` 최소 typed model
- `Observation` 최소 typed model
- validation 강제
- append-only `EventLedger`와의 연결
- 최소 이벤트 타입 정의
- `v2-spring run events <run-id>` CLI 추가
- 테스트 추가
- ADR / 설계 문서 / implementation note 반영

## 구현하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- task/module planner
- human-in-loop UI
- approval workflow 전체
- full event sourcing
- Redis coordination
- CrewAI / LangGraph 통합
- artifact registry 전체
- run replay / cancel / resume 전체 루프

## 구체 작업 항목 체크리스트

- [ ] `Decision` 최소 typed model 정의
- [ ] `Observation` 최소 typed model 정의
- [ ] `Enum` / validation 규칙 추가
- [ ] `Decision` / `Observation`을 ledger 이벤트로 기록할 수 있게 연결
- [ ] 최소 이벤트 타입 정의
- [ ] `v2-spring run events <run-id>` CLI 구현
- [ ] run의 사건 흐름을 시간순으로 출력 가능하게 구현
- [ ] invalid input에 대한 validation 실패 테스트 추가
- [ ] events 출력 포맷 테스트 추가
- [ ] ADR 작성 또는 갱신
- [ ] implementation note 작성
- [ ] Step 2가 Step 1과 어떻게 연결되는지 문서 반영

## Acceptance Criteria

- `Decision`과 `Observation`이 dict가 아니라 typed/validated model로 저장됩니다.
- `Decision` / `Observation` 관련 이벤트가 `EventLedger`에 append-only로 남습니다.
- `v2-spring run events <run-id>`를 실행하면 해당 run의 사건 흐름을 확인할 수 있습니다.
- run의 decision / observation history가 CLI에서 사람이 읽을 수 있게 출력됩니다.
- validation 실패 시 명확한 에러가 납니다.
- 테스트가 통과합니다.
- 문서와 실제 구현이 일치합니다.

## 리스크 / 메모

- `Decision` / `Observation`을 너무 크게 잡으면 Step 2가 무거워집니다.
- Step 1과 Step 2의 경계가 흐려지면 ledger 설계가 다시 흔들릴 수 있습니다.
- 출력 포맷은 founder가 읽을 수 있어야 하므로, raw dump보다 구조화된 요약이 우선입니다.
- 이번 단계는 "더 많이 저장"이 아니라 "더 잘 검증 가능하게 저장"이 목적입니다.

## 연결 문서 / ADR

- `docs/architecture/EXECUTION_PLAN.md`
- `docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md`
- `docs/adr/0003-core-state-model.md`
- `docs/adr/0004-deterministic-substrate.md`

원하면 다음으로 바로 Step 3용 `[인프라]` 또는 `[코어]` 이슈를 이어서 만들 수 있어야 합니다.
