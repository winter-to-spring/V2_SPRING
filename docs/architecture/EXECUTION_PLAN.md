# V2_SPRING 실행 계획

## 의도

V2_SPRING은 자율 소프트웨어 스튜디오를 클린룸 방식으로 다시 만드는
프로젝트입니다.

우리는 V1을 제품 코어로 그대로 끌고 가지 않습니다. 이전 작업에서 검증된
아이디어, 문서, 인프라 방향만 선별해 재사용합니다.

## Phase 1. 차터와 경계

목표:
- 구현이 다시 커지기 전에 시스템 차터를 잠근다

산출물:
- 시스템 목적과 비목표
- human-in-the-loop 경계
- "자율적이지만 통제 가능한가"에 대한 성공 기준
- 초기 ADR 세트

이 단계가 답해야 할 질문:
- 제품은 실제로 무엇을 위한 것인가
- 어떤 결정은 계속 사람이 승인해야 하는가
- 무엇은 절대 agent memory에 의존하면 안 되는가

## Phase 2. 핵심 상태 모델

목표:
- 오케스트레이션을 만들기 전에 안정적인 도메인 모델을 정의한다

핵심 엔티티:
- Project
- Run
- Module
- Task
- Capability
- Decision
- Artifact
- Approval
- Budget
- Risk
- Observation

산출물:
- 도메인 모델
- 라이프사이클 정의
- 불변식
- 이벤트 원장 설계

이 단계가 답해야 할 질문:
- 진실의 원천은 무엇인가
- agent 수가 늘어나면 무엇이 바뀔 수 있는가
- agent가 많이 늘어나도 무엇은 반드시 invariant로 남아야 하는가

## Phase 3. 결정론적 substrate

목표:
- 신뢰할 수 있는 system of record를 먼저 만든다

범위:
- 기록 저장소로 Postgres
- 조정 수단으로 Redis
- queue와 lease semantics
- approval과 budget 정책
- cancellation, retry, resume semantics

산출물:
- 앱 골격
- 인프라 부트스트랩
- 결정론적 executor 계약
- 이벤트 저장과 replay 기반

이 단계가 답해야 할 질문:
- 상태는 어떻게 저장되는가
- 동시 실행은 어떻게 안전하게 유지되는가
- run은 어떻게 종료/일시정지/재개/취소되는가

## Phase 4. Planner And Replanner Layer

목표:
- 하드코딩 라우팅에서 action selection으로 이동한다

범위:
- state snapshot
- possible actions
- policy guard
- planner output schema
- replanning loop

주요 타깃:
- planner와 replanner로서의 LangGraph

이 단계가 답해야 할 질문:
- 다음 행동은 어떻게 생성되는가
- risk와 approval은 planning에 어떻게 영향을 주는가
- blocker나 feedback 이후 시스템은 어떻게 run으로 재진입하는가

## Phase 5. Execution Workforce

목표:
- substrate를 바꾸지 않고 specialist execution crew를 붙인다

범위:
- capability registry
- execution pool
- module builder
- QA / integration worker

주요 타깃:
- execution workforce로서의 CrewAI

이 단계가 답해야 할 질문:
- 어떤 task에 누가 적합한가
- agent 추가는 topology가 아니라 capacity를 어떻게 바꾸는가
- execution feedback은 planner로 어떻게 돌아오는가

## Phase 6. Founder Verification Surface

목표:
- 사람이 raw log를 읽지 않고도 전체 과정을 검사할 수 있게 만든다

범위:
- 요청 입력
- live process trail
- approval interaction
- artifact/result 저장
- run history와 replay

이 단계가 답해야 할 질문:
- 무엇이 요청되었는가
- 어떻게 처리되었는가
- 누가 작업했는가
- 어떤 문서와 artifact가 생산되었는가
- 어떤 리스크가 남아 있는가

## Phase 7. 자율성 확장

목표:
- 통제를 잃지 않고 bounded autonomy를 확장한다

범위:
- hiring proposal flow
- budget review flow
- observer role
- external health monitoring
- self-improvement loop

이 단계가 답해야 할 질문:
- 시스템은 무엇을 스스로 결정할 수 있는가
- 언제 에스컬레이션해야 하는가
- founder intent에서 벗어나지 않으면서 어떻게 스스로를 개선하는가

## 즉시 우선순위

우리는 다음부터 시작해야 합니다.
1. Phase 1 차터
2. Phase 2 상태 모델
3. Phase 3 결정론적 substrate

planner, crew, UI는 이 세 기반 위에 올라가야 합니다.
