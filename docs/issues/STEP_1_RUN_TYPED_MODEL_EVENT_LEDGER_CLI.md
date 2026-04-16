# [V2_SPRING] Step 1 - Run typed model + append-only EventLedger + CLI tracer bullet

## 배경 / 문제

V2_SPRING은 사람과 에이전트가 함께 검증 가능한 자율형 조직 운영체계를 만드는 프로젝트입니다.

그런데 지금 가장 먼저 필요한 것은 화려한 기능이 아니라, **CLI만으로도 직접 검증 가능한 최소 루프의 첫 조각**입니다.

이번 단계에서 확인하고 싶은 것은 단순합니다.

- 요청이 구조화된 `Run`으로 생성되는가
- 그 생성 사실이 불변의 기록으로 남는가
- 사람이 CLI로 직접 조회해서 확인할 수 있는가

지금까지의 교훈도 분명합니다.

- 상태가 `dict`처럼 느슨하면 에이전트 수가 늘수록 해석이 흔들립니다.
- 실행 결과가 콘솔 로그에만 남으면 사람이 실제 상태를 검증할 수 없습니다.
- full event sourcing는 지금 단계에서 과합니다.
- 하지만 **state tables + append-only event ledger hybrid**는 충분히 작고, 충분히 강합니다.

그래서 Step 1에서는 `Run` 엔티티를 typed/validated하게 만들고, 최소한의 append-only 이벤트 기록과 CLI 조회 루프를 먼저 세웁니다.

---

## 이번 단계의 목적

이번 단계의 목적은 아래 5가지입니다.

1. `Run`의 구조를 먼저 고정합니다.
2. `RUN_CREATED` 이벤트를 append-only ledger에 남깁니다.
3. `v2-spring run create`와 `v2-spring run show <run-id>`로 최소 검증 루프를 만듭니다.
4. 사람이 눈으로 "생성됨 -> 조회됨"을 확인할 수 있게 합니다.
5. 이후 `Task / Approval / Artifact / Replay`로 확장할 수 있는 기반을 만듭니다.

---

## 구현 범위

이번 이슈는 아래 범위까지만 포함합니다.

- `Run` 엔티티의 typed/validated 모델 도입
- `dict` 기반 느슨한 모델 금지
- Enum 및 validation 강제
- append-only `EventLedger` 도입
- 최소 이벤트 `RUN_CREATED` 포함
- CLI tracer bullet 1차
  - `v2-spring run create`
  - `v2-spring run show <run-id>`
- 관련 테스트 추가
- ADR / 설계 문서 / implementation note 반영

---

## 이번 단계에서 하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- full event sourcing
- `Task` / `Module` planner
- LangGraph / CrewAI 연결
- human-in-the-loop 승인 UI
- budget policy
- Redis coordination
- queue / lease / retry / resume semantics
- artifact registry 전체 구현
- founder verification surface 전체 UI
- run replay 전체 구현

즉, 이번 단계는 **최소 코어 루프를 증명하는 tracer bullet**에만 집중합니다.

---

## 구체 작업 항목

- [ ] `Run` typed model 정의
- [ ] `RunStatus`, `RiskLevel`, `UrgencyLevel` 등 필요한 Enum 정의
- [ ] validation 규칙 추가
- [ ] `dict` 기반 느슨한 입력 차단
- [ ] append-only `EventLedger` 스키마 정의
- [ ] `RUN_CREATED` 이벤트 타입 정의
- [ ] `run create` CLI 구현
- [ ] `run show <run-id>` CLI 구현
- [ ] state table과 ledger insert 흐름 연결
- [ ] 최소 persistence 연결
- [ ] 생성/조회 흐름 테스트 작성
- [ ] invalid input validation 실패 테스트 작성
- [ ] ADR 반영 또는 갱신
- [ ] implementation note 작성
- [ ] phase 1 baseline 문서에 이 작업 링크 반영

---

## Acceptance Criteria

아래 조건을 모두 만족하면 이번 단계는 완료로 봅니다.

- `v2-spring run create`를 실행하면 새 `Run`이 생성된다.
- 생성된 `Run`은 typed/validated 모델을 통과해야 한다.
- `RUN_CREATED` 이벤트가 append-only ledger에 기록된다.
- `v2-spring run show <run-id>`로 해당 run의 핵심 상태를 확인할 수 있다.
- invalid input은 validation error로 거절된다.
- `dict` 기반 느슨한 입력으로는 run이 생성되지 않는다.
- 테스트가 통과한다.
- ADR / 문서가 실제 구현 내용과 일치한다.
- 사람이 CLI만 보고도 "생성되었고 조회된다"를 검증할 수 있다.

---

## 리스크 / 메모

- full event sourcing를 지금 억지로 넣으면 복잡도만 커집니다.
- ledger와 state table의 책임 경계를 초기에 잘못 잡으면 나중에 replay/consistency가 꼬일 수 있습니다.
- `Run`을 너무 넓게 잡으면 Step 1이 무거워질 수 있습니다.
- 이번 단계의 핵심은 **작게, 명확하게, 검증 가능하게** 가는 것입니다.
- 이후 phase에서 `Task / Approval / Artifact / Replay`를 얹을 수 있도록 schema를 너무 경직되지 않게 설계해야 합니다.

---

## 연결 문서 / ADR

- `docs/architecture/EXECUTION_PLAN.md`
- `docs/charter/FINAL_DIRECTION.md`
- `docs/charter/SYSTEM_CHARTER.md`
- `docs/specs/TRACER_BULLET.md`
- `docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md`
- `docs/adr/0003-core-state-model.md`
- `docs/adr/0004-deterministic-substrate.md`

이번 단계가 끝나면 다음으로
- `Task / Decision / Artifact / Approval` 확장
- `run replay`
- human-in-the-loop CLI
순으로 이어갈 수 있어야 합니다.
