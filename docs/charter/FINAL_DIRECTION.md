# V2_SPRING 최종 방향성

## 최종 방향

V2_SPRING은 Paperclip 기반 V1 시스템을 보수적으로 이어 붙인 형태가
아닙니다.

다음 아키텍처를 기준으로 한 클린룸 재구축입니다.

- **우리의 control plane**이 system of record가 된다
- **LangGraph**가 planner / replanner 계층을 맡는다
- **CrewAI**가 execution workforce 계층을 맡는다
- **Human-in-the-loop governance**가 hiring, budget, destructive change,
  scope expansion을 통제한다
- **Founder verification surface**는 ledger를 대체하지 않고, ledger 위에
  올라간다

첫 번째 마일스톤은 완성형 제품이 아닙니다.  
첫 번째 마일스톤은 **CLI에서 검증 가능한 tracer bullet**입니다.

## 우리가 만들고 있는 것

우리는 founder가 통제할 수 있는 자율 소프트웨어 스튜디오를 만들고
있습니다.

이 말은 곧:
- 사람이 목표를 준다
- 시스템이 계획하고 재계획한다
- 실행 워커가 bounded work를 수행한다
- 중요한 결정이 기록된다
- 위험한 행동은 승인이 필요하다
- 결과는 검사 가능하고 replay 가능하다

## 우리가 만들지 않는 것

우리는 다음을 만들지 않습니다.
- 선형 워크플로우 엔진
- UI-first 데모 껍데기
- 오케스트레이션인 척하는 프롬프트 더미
- agent memory가 source of truth인 시스템
- planner logic과 state mutation이 뒤섞인 시스템

## 채택한 원칙

### 1. Ledger First

진실의 원천은 영속적인 구조화 상태입니다.
- Run
- Task
- Decision
- Artifact
- Approval
- Risk
- Budget
- Observation

자연어 요약은 진실의 원천이 아닙니다.

### 2. Planner / Executor Separation

planner는 다음을 할 수 있습니다.
- 상태를 조회한다
- 다음 행동을 제안한다
- 대안을 우선순위화한다
- 승인을 요청한다

planner는 다음을 할 수 없습니다.
- 영속 상태를 직접 변경한다

상태 변경은 결정론적 executor만 할 수 있습니다.

### 3. Human Approval Is Core, Not Optional

다음 항목에는 승인이 필수입니다.
- 새 agent 채용
- budget 증가
- destructive change
- scope expansion
- 그 외 governance가 정의한 고위험 행동

### 4. Replayability Is Required

모든 run은 저장된 기록으로부터 replay 가능해야 합니다.
사람은 다음을 재구성할 수 있어야 합니다.
- 무엇이 요청되었는지
- 무엇이 결정되었는지
- 무엇이 실행되었는지
- 무엇이 승인되었는지
- 어떤 artifact가 만들어졌는지
- 왜 run이 종료되었는지

### 5. Verification Before Surface Polish

founder용 UI가 주요 작업이 되기 전에, 시스템은 CLI와 DB 증거만으로도
정확성이 증명 가능해야 합니다.

## 우리가 받아들이고 완화하는 주요 리스크

### 리스크 1. 상태 불일치

완화 방식:
- 결정론적 상태 전이
- planner는 상태를 직접 변경할 수 없음
- execution receipt를 artifact와 observation으로 기록
- replay 검증

### 리스크 2. Token Bankruptcy

완화 방식:
- 전체 ledger는 저장하되, planner는 snapshot과 summary만 읽음
- 메모리 관리를 명시적으로 처리
- planner context를 bounded하게 유지

### 리스크 3. LangGraph / CrewAI Impedance Mismatch

완화 방식:
- 두 프레임워크는 직접 서로 통합하지 않음
- 둘 다 우리 계약을 통해 통합함
- control plane이 중심을 유지함

### 리스크 4. UI Over-Engineering

완화 방식:
- UI-first 마일스톤 금지
- 첫 마일스톤은 CLI 검증 가능 상태
- founder UI는 tracer bullet 증명 이후

## 기술 방향

### System of Record
- 영속 기록은 Postgres
- 조정, 큐, lease, wake-up semantics는 Redis

### Cognition Layer
- LangGraph는 다음을 담당
  - planning
  - replanning
  - possible action 선택
  - rejection 또는 blockage 이후 재진입

### Execution Layer
- CrewAI는 다음을 담당
  - bounded specialist work
  - builder crew
  - QA crew
  - reviewer / integration crew

### Verification Layer
- 우선은 CLI
- replay와 event inspection
- founder surface는 나중

## 즉시 빌드 순서

1. 차터와 경계
2. 핵심 상태 모델
3. 결정론적 substrate
4. CLI tracer bullet
5. planner 계약
6. executor 계약
7. LangGraph 통합
8. CrewAI 통합
9. founder verification UI

## 최종 약속

V2_SPRING은 공식적으로 다음과 같은 시스템입니다.

**상태 기반, 원장 기반, planner/executor 분리, 사람 거버넌스 중심의 자율 소프트웨어 스튜디오**

첫 번째 성공 증거는 세련된 UI가 아닙니다.  
첫 번째 성공 증거는 다음이 가능한 run입니다.
- CLI에서 생성된다
- 계획된다
- 하나의 bounded worker에 의해 실행된다
- 사람이 승인한다
- ledger로부터 replay된다
