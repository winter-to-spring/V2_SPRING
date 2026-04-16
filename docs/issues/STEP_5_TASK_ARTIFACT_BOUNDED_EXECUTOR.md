# [코어] Step 5 - Task typed model + Artifact typed model + bounded executor CLI

## 배경 / 문제

Step 4까지 오면서 V2_SPRING은 CLI에서 다음을 직접 검증할 수 있게 됐습니다.

- run이 생성되는지
- observation / decision / approval이 구조화되어 남는지
- approval이 human-in-the-loop 경계로 실제로 동작하는지
- approval barrier가 explicit error와 audit visibility를 함께 보장하는지

하지만 아직 중요한 한 조각이 비어 있습니다.

바로 **실제로 수행된 작업(Task)과 그 결과물(Artifact)** 입니다.

지금 상태에서는 run이 만들어지고 승인도 처리할 수 있지만, “그래서 실제로 무슨 일을 했고 어떤 결과가 나왔는지”를 구조화해서 남기지 못합니다.

이번 단계는 이 공백을 아주 작고 안전한 방식으로 메웁니다.

한 번에 많은 걸 하려는 게 아니라,

- approval 이후
- 딱 1개의 bounded task를 수행하고
- 딱 1개의 artifact를 남기고
- 그 과정을 CLI로 검증 가능하게 만드는 것

여기까지만 증명하는 단계입니다.

## 이번 단계의 목적

1. `Task`를 typed/validated model로 도입합니다.
2. `Artifact`를 typed/validated model로 도입합니다.
3. approval 이후 bounded executor가 안전한 작업 1개를 실제로 수행하게 합니다.
4. task lifecycle과 artifact 생성 결과를 append-only ledger에 남깁니다.
5. founder가 CLI만으로 “무슨 작업을 했고 무엇이 나왔는지”를 직접 확인할 수 있게 합니다.

## 구현 범위

이번 단계에서는 아래 범위까지만 포함합니다.

- `Task` 최소 typed model
- `TaskStatus` 등 필요한 Enum 및 validation
- `Artifact` 최소 typed model
- `TaskExecutionReceipt` 또는 이에 준하는 실행 메타데이터 구조
- approval 이후 수행 가능한 bounded executor 1개
- 최소 task lifecycle
  - `created`
  - `ready`
  - `running`
  - `completed`
  - `failed`
- append-only ledger 이벤트 추가
  - `TASK_CREATED`
  - `TASK_STARTED`
  - `TASK_COMPLETED`
  - `TASK_FAILED`
  - `ARTIFACT_RECORDED`
- CLI
  - `v2-spring task list --run <run-id>`
  - `v2-spring artifact list --run <run-id>`
  - `v2-spring run execute <run-id>` 또는 이에 준하는 bounded execution 명령
- 관련 테스트 추가
- ADR / 설계 문서 / implementation note 반영

## bounded task의 권장 형태

이번 단계의 bounded task는 위험한 변경이 아닌 **읽기 중심 작업**이어야 합니다.

권장 예시는:

- repository tree 읽기
- 짧은 구조 요약 작성
- 결과를 text artifact로 저장

즉 이번 단계의 목표는 “코드를 크게 바꾸는 것”이 아니라, **실제로 수행된 일과 생성된 결과물이 구조화되어 남는지**를 증명하는 것입니다.

### bounded executor 안전 조건

이번 단계의 executor는 아래 안전 조건을 반드시 가져야 합니다.

- 기본은 **read-only**
- 허용된 작업 디렉토리 안에서만 실행
- `.env`, `.git`, 시스템 민감 경로는 읽기 대상에서 제외하거나 명시적으로 차단
- timeout을 가져야 함
- stdout / stderr를 execution receipt에 남겨야 함

즉 이번 단계에서의 executor는 “아무거나 실행하는 도구”가 아니라, **매우 좁게 제한된 읽기형 실행기**여야 합니다.

## 이번 단계에서 하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- multi-task orchestration
- planner / replanner 전체 연결
- LangGraph 통합
- CrewAI execution pool
- Redis coordination 전체
- queue / lease / retry / resume semantics 전체
- full replay viewer
- UI / founder surface
- dynamic hiring / budget flow
- 코드 수정형 executor 확장
- DB-level or distributed lock
- multi-worker concurrency hardening 전체
- 대용량 artifact blob 저장

이번 단계에서는 **filesystem pointer + metadata** 중심으로 artifact를 다루고, 무거운 저장 전략은 뒤로 미룹니다.

즉 이번 단계는 **bounded execution 한 번 + artifact 한 번**까지만 증명합니다.

## 구체 작업 항목 체크리스트

- [ ] `Task` 최소 typed model 정의
- [ ] `TaskStatus` / 관련 Enum 정의
- [ ] `Artifact` 최소 typed model 정의
- [ ] `TaskExecutionReceipt` 또는 동등한 실행 메타데이터 구조 정의
- [ ] validation 규칙 추가
- [ ] task state table 도입
- [ ] artifact state table 도입
- [ ] ledger event 타입 추가
- [ ] bounded executor contract 정의
- [ ] executor timeout 정의
- [ ] stdout / stderr capture 추가
- [ ] read-only / allowed-path 정책 추가
- [ ] approval 이후에만 실행되는 guard 추가
- [ ] `task list` CLI 구현
- [ ] `artifact list` CLI 구현
- [ ] bounded execution CLI 구현
- [ ] artifact metadata에 provenance 필드 추가
  - `task_id`
  - `run_id`
  - `execution_context_id`
  - `storage_kind`
  - `sha256`
  - `size_bytes`
  - `command`
  - `cwd`
- [ ] task / artifact / ledger 원자성 규칙 명시
- [ ] task lifecycle 테스트 추가
- [ ] artifact 생성 테스트 추가
- [ ] approval 없이는 실행되지 않는 테스트 추가
- [ ] timeout / failed execution 테스트 추가
- [ ] artifact hash 및 linkage 테스트 추가
- [ ] implementation note 작성
- [ ] tracer bullet 문서 갱신

## Acceptance Criteria

- approval이 완료된 run에 대해 bounded task 1개를 실행할 수 있습니다.
- `Task`는 typed/validated model로 저장됩니다.
- `Artifact`는 typed/validated model로 저장됩니다.
- `Artifact`는 provenance metadata를 반드시 포함합니다.
- artifact에는 파일 내용 또는 결과물의 `sha256` 해시가 저장됩니다.
- task lifecycle이 ledger에 append-only로 기록됩니다.
- artifact 생성이 ledger에 append-only로 기록됩니다.
- task / artifact / ledger가 서로 인과관계로 연결됩니다.
- CLI에서 task 목록과 artifact 목록을 조회할 수 있습니다.
- approval 없이 executor를 실행하려고 하면 명시적 에러로 거절됩니다.
- bounded executor가 timeout 또는 실패하면 명시적 실패 상태와 실행 로그가 남습니다.
- 테스트가 통과합니다.
- 문서와 실제 구현이 일치합니다.

## 리스크 / 메모

- bounded executor를 너무 똑똑하게 만들면 Step 5가 무거워질 수 있습니다.
- 이번 단계의 핵심은 execution breadth가 아니라 execution proof입니다.
- artifact를 raw blob처럼 다루지 말고, 나중 replay와 founder verification에 쓸 수 있게 최소 메타데이터를 같이 남겨야 합니다.
- artifact는 path pointer + metadata 중심으로 시작하는 것이 안전합니다.
- checksum / execution_context_id / command / cwd가 없으면 replayability가 약해집니다.
- task와 ledger 기록의 원자성이 깨지면 “일은 끝났는데 기록은 없다”는 최악의 상태가 생깁니다.
- service-level guard만으로는 나중 동시성 문제가 남을 수 있으므로, 이 부분은 별도 리스크로 추적해야 합니다.
- approval 이후 자동으로 여러 task가 이어지는 구조는 아직 넣지 않습니다.
- 지금은 “한 번의 실행이 구조화되어 남는다”를 증명하는 것이 가장 중요합니다.

## 연결 문서 / ADR

- `docs/architecture/EXECUTION_PLAN.md`
- `docs/specs/TRACER_BULLET.md`
- `docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md`
- `docs/adr/0003-core-state-model.md`
- `docs/adr/0004-deterministic-substrate.md`
- `docs/adr/0005-founder-verification-surface.md`

이번 단계가 끝나면 다음으로

- `run replay`
- planner 가능한 action selection
- executor receipt 고도화

순으로 이어갈 수 있어야 합니다.
