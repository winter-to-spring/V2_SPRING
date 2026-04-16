# Agent Studio 최종 기획보고서

Updated: 2026-04-10 (Asia/Seoul)

## 1. 문서 목적

본 문서는 `Agent Studio` 프로젝트의 최종 기획 방향을 정리한 기준 문서이다.

이 문서는 다음 목적을 가진다.

- 프로젝트가 무엇을 만들려는지 명확히 정의한다.
- 검토한 방향과 선택지를 정리한다.
- 최종적으로 어떤 구조를 채택했는지 설명한다.
- 기술 스택과 역할 분담 기준을 확정한다.
- 버전별 로드맵과 v1 개발 착수 범위를 명시한다.

본 문서는 향후 개발 진행의 기준 문서로 사용한다.

## 2. 프로젝트 정의

### 2.1 프로젝트 한 줄 정의

`Agent Studio`는 아이디어와 요구사항을 입력으로 받아, PRD 작성, 기술 계획, 작업 분해, 구현, 검증, 문서화, 승인까지 이어지는 전체 개발 흐름을 AI 에이전트 중심으로 운영하는 `비즈니스용 개인형 AI 개발 운영체계`이다.

### 2.2 우리가 만들려는 것

우리가 만들려는 것은 단순한 AI 코딩 도구가 아니다.

우리가 만들려는 것은 다음 조건을 만족하는 운영 시스템이다.

- 요구사항을 구조화한다.
- 역할별 에이전트가 분업한다.
- 상태, 로그, 산출물, 승인 기록이 남는다.
- QA와 품질 게이트가 내장된다.
- 고위험 구간은 반드시 사람 승인을 거친다.
- 실제 비즈니스 운영에 투입 가능한 수준으로 확장 가능하다.

### 2.3 만들지 않으려는 것

다음은 본 프로젝트의 직접적인 목표가 아니다.

- 완전 자율적으로 회사 전체를 운영하는 시스템
- 단순 데모용 멀티에이전트 쇼케이스
- 코드 생성 성능만 강조한 실험 프로젝트
- 초기에 과도한 인프라와 역할을 모두 도입하는 구조

## 3. 최종 목표

본 프로젝트의 최종 목표는 `1인 개발 스튜디오가 AI 팀을 두고 실제 개발회사처럼 운영되는 체계`를 만드는 것이다.

최종적으로는 다음이 가능해야 한다.

1. 아이디어 또는 요구사항을 받는다.
2. 이를 PRD와 기술 계획으로 변환한다.
3. 작업을 역할별 에이전트에 분배한다.
4. 구현과 검증을 반복 수행한다.
5. 모든 과정에 품질 게이트를 적용한다.
6. 위험한 경계에서는 사람 승인을 받는다.
7. 결과를 문서, 이슈, 코드, 리포트, 승인 이력으로 남긴다.

즉, 최종 목표는 `AI가 개발을 도와주는 수준`이 아니라 `AI 개발 운영 시스템을 실제로 운영하는 수준`이다.

## 4. 방향 검토와 의사결정

프로젝트 방향을 정하기 위해 다섯 가지 축을 검토하였다.

### 4.1 제품형 비동기 코딩 에이전트

검토 이유:

- 비즈니스 사용자는 대화형보다 비동기 작업형 UX를 더 다루기 쉽다.
- 작업을 보낸 뒤 상태와 결과를 추적하는 구조가 운영에 적합하다.

채택 요소:

- 작업 큐형 흐름
- 상태 표시
- 로그 추적
- PR 및 리뷰 루프
- 승인 후 다음 단계 진행

최종 판단:

- UX 관점에서는 채택
- 내부 로직은 별도 오케스트레이션 필요

### 4.2 오픈소스 SWE 에이전트

검토 이유:

- 코드 수정, 테스트 실행, issue-to-fix 루프가 강점이기 때문
- 구현 루프와 자동 검증 루프 설계에 직접적인 도움이 되기 때문

채택 요소:

- 도구 사용 기반 구현
- 실행 결과 기반 판정
- 실패 시 재시도
- 테스트 중심 검증

최종 판단:

- 실행 패턴은 적극 차용
- 제품 운영, 승인, 문서, 거버넌스는 별도 설계

### 4.3 멀티에이전트 오케스트레이션

검토한 선택지:

- `LangGraph 중심`
- `LangChain 중심`
- `n8n 중심`

비교 결과:

- `LangGraph`는 상태 기반 long-running workflow와 human-in-the-loop에 적합하다.
- `LangChain`은 유용한 상위 추상화이지만, 코어 상태머신 자체를 담당시키기에는 복잡도를 키울 수 있다.
- `n8n`은 외부 연결과 운영 자동화에 강하지만, 코어 에이전트 상태 전이를 모두 맡기기에는 책임이 과도해진다.

최종 결정:

- 코어는 `LangGraph 중심`
- `LangChain`은 최소 사용
- `n8n`은 운영 자동화 레이어로 사용

### 4.4 운영 및 승인 레이어

검토한 선택지:

- 모든 운영 로직을 애플리케이션 코드에 직접 구현
- 운영 자동화는 외부 워크플로우 툴로 분리

비교 결과:

- 직접 구현 방식은 코드량과 유지보수 부담이 빠르게 커진다.
- 운영 자동화 분리 방식은 알림, 웹훅, 스케줄, 문서 동기화, 승인 요청을 효율적으로 다룰 수 있다.

최종 결정:

- 운영 자동화는 `n8n`
- 핵심 상태 전이와 판단은 `LangGraph`

### 4.5 평가와 성공 기준

검토한 방향:

- 모델 성능 중심 평가
- 비즈니스 운영 성능 중심 평가

최종 결정:

- 단순 모델 성능보다 운영 신뢰성 중심으로 평가한다.

주요 평가 기준:

- 작업 성공률
- 품질 게이트 통과율
- 승인 전 오류 검출률
- 실패 복구율
- 재시도 효율
- 상태 추적 가능성
- 운영 비용 대비 성과

## 5. 최종 방향 요약

본 프로젝트는 다음 네 방향을 결합한 구조로 확정한다.

- `비동기 코딩 에이전트형 UX`
- `오픈소스 SWE 에이전트형 실행 루프`
- `LangGraph 중심 멀티에이전트 오케스트레이션`
- `n8n 기반 운영/승인 자동화`

이를 통해 `비즈니스용 개인형 AI 개발 운영체계`를 구축한다.

## 6. 프로세스 성격

### 6.1 Waterfall vs Agile

본 프로젝트는 순수 Waterfall도 아니고 순수 Agile도 아니다.

최종적으로는 `Stage-gated Agile`을 채택한다.

의미는 다음과 같다.

- 요구사항과 계획은 구조화한다.
- 구현과 수정은 짧은 반복 루프로 운영한다.
- 외부 영향이 큰 구간은 승인 게이트로 통제한다.

즉:

- 앞단은 계획형
- 중간은 반복형
- 뒷단은 승인형

### 6.2 SDLC 반영 방식

본 시스템은 다음 SDLC를 반영한다.

1. 요구사항 수집
2. PRD 작성
3. 요구사항 승인
4. 기술 계획 수립
5. 작업 분해
6. 구현
7. 비평 및 리뷰
8. QA 검증
9. 문서 및 기록 정리
10. 승인 대기
11. 완료 또는 릴리즈 준비

현재 문서는 `요구사항 -> 구현 -> 검증 -> 승인` 흐름이 중심이며, 운영 이후의 incident/postmortem 루프는 v2 이후 강화 대상으로 둔다.

## 7. 핵심 설계 원칙

본 프로젝트는 다음 원칙을 기준으로 설계한다.

### 7.1 Workflow over Chaos

- 자유 대화형이 아니라 명시적 워크플로우로 운영한다.

### 7.2 Artifacts over Chat

- 채팅보다 문서, 이슈, 계약서, 리포트, PR을 중심 산출물로 삼는다.

### 7.3 Tests before Trust

- 코드 생성 자체를 완료로 보지 않는다.
- 명시적 검증 통과 후에만 완료로 판정한다.

### 7.4 Human Approval at Risk Boundaries

- 요구사항 확정, 보안, 외부 영향, 데이터 삭제, 배포는 사람 승인을 요구한다.

### 7.5 Narrow Roles

- 각 에이전트는 작은 책임과 작은 쓰기 범위를 가진다.

### 7.6 Stateful Observability

- 각 작업과 에이전트는 상태, heartbeat, last action, blocker를 드러내야 한다.

## 8. 레이어별 아키텍처

본 시스템은 다음 레이어를 기준으로 설계한다.

### 8.1 Business Layer

정의:

- 무엇을 자동화할지 결정
- 어디서 사람 승인을 넣을지 규정
- 비즈니스 리스크 경계 정의

### 8.2 Workflow Layer

정의:

- 작업 단계 정의
- 상태 전이 규칙 정의
- 실패 시 escalation 규칙 정의

### 8.3 Agent Layer

정의:

- Manager, PM, Builder, QA 등 역할 분리
- 책임과 쓰기 범위 제한

### 8.4 Execution Layer

정의:

- LangGraph 기반 오케스트레이션
- pause, resume, retry, escalation 처리

### 8.5 Integration Layer

정의:

- GitHub, Notion, Playwright, Slack, Figma, n8n 연동

### 8.6 State Layer

정의:

- 상태와 승인, 감사 이력 저장
- queue 및 cache 확장 포인트 확보

### 8.7 Quality Layer

정의:

- lint, typecheck, unit, smoke, integration, E2E 등 품질 게이트 운영

### 8.8 Observability Layer

정의:

- event log, heartbeat, retry count, blocker, dashboard source data 관리

## 9. 역할 구조

### 9.1 기본 역할군

- `Manager`: 작업 라우팅, 상태 전이, 오너십 관리
- `PM`: PRD 작성, 요구사항 정리, acceptance criteria 정의
- `Architect`: 기술 계획, API contract, 모듈 경계 정의
- `Frontend`: UI 범위 구현
- `Backend`: API/DB/서비스 범위 구현
- `Critic`: diff 리뷰, 리스크 검출, 계약 불일치 점검
- `QA`: 테스트 실행, 결과 판정, 품질 게이트 집행
- `Docs/Release`: changelog, release note, 문서 동기화

### 9.2 v1 역할 축소

v1은 과설계를 피하기 위해 다음 네 역할로 시작한다.

- `Manager`
- `PM`
- `Builder`
- `QA`

이후 v2에서 Builder를 FE/BE로 분리하고 Critic, Docs/Release를 추가한다.

## 10. 도구와 시스템 역할 분담

### 10.1 GitHub / Notion / n8n 분담

최종 분담은 다음과 같다.

#### GitHub는 실행의 정본

- Issues
- Projects
- Branches
- Pull Requests
- Reviews
- Releases

#### Notion은 비즈니스 컨텍스트의 정본

- Product Inbox
- PRD
- Roadmap overview
- Decision logs
- Runbooks
- Research notes
- Business-facing release summaries

#### n8n은 연결과 자동화의 정본

- request intake
- sync automation
- alerts and reminders
- recurring jobs
- approval routing

### 10.2 산출물 기준

최소 산출물은 다음과 같이 정의한다.

- `docs/PRD.md`
- `docs/ROADMAP.md`
- `contracts/API_CONTRACT.yaml`
- GitHub Issues linked to PRD
- Pull Request linked to Issue
- `docs/TEST_REPORT.md`
- `CHANGELOG.md`
- `docs/RELEASE_NOTES.md`

## 11. 품질 게이트와 QA 구조

### 11.1 QA의 위치

QA는 마지막 단계의 부가 기능이 아니라 시스템 중심 축이다.

QA는 최소 세 단계에 개입한다.

1. `Task QA`
2. `Merge QA`
3. `Release QA`

### 11.2 Module Gate

각 구현 단위는 최소한 다음을 통과해야 한다.

1. `lint`
2. `typecheck`
3. `unit test`
4. `module smoke test`
5. `contract conformance check`

### 11.3 Integration Gate

통합 단계에서는 다음을 확인한다.

1. application boot
2. env validation
3. migration verification
4. API health check
5. integration scenarios
6. Playwright happy path

### 11.4 Release Gate

승인 직전에는 다음을 확인한다.

1. changelog updated
2. release notes drafted
3. issue and PR linkage complete
4. founder approval recorded

## 12. 승인 경계

### 12.1 완전 자동 가능 영역

- PRD first draft
- issue decomposition
- scaffold generation
- low-risk docs update
- lint/typecheck/unit test execution
- draft changelog generation

### 12.2 사람 검토 필수 영역

- final PRD approval
- pricing, billing, auth, security 관련 변경
- destructive DB changes
- production release
- deletion of data or content
- external-facing docs or communication
- secrets or permission changes

### 12.3 Hard Stop 영역

다음은 항상 사람 확인이 필요하다.

- production deployment
- data deletion
- payment action
- permission model change
- third-party credential rotation
- external email blast

## 13. 기술 스택 최종 결정

### 13.1 Core Orchestration

- `LangGraph`

선정 이유:

- long-running workflow에 적합
- 상태 전이 제어에 강함
- human-in-the-loop 구현에 적합
- retry, pause, resume 구조 설계에 유리

### 13.2 Utility and Model Layer

- `LangChain` 최소 사용

선정 이유:

- 모델 및 도구 연결에만 활용
- 코어 오케스트레이션 복잡도 증가 방지

### 13.3 Source of Truth and Audit

- `Postgres` 또는 `Supabase`

역할:

- request state
- execution metadata
- approvals
- audit history
- dashboard data source

최종 판단:

- 시스템 정본은 Postgres 계열로 둔다.

### 13.4 Queue / Cache / Runtime Utility

- `Redis`

역할:

- ephemeral queue
- cache
- Pub/Sub
- distributed lock
- idempotency helper
- heartbeat freshness check

최종 판단:

- 비즈니스용 확장 단계에서는 필요성이 높다.
- 그러나 `v1 필수`로 두지 않는다.
- `v2부터` queue mode, worker 분리, 동시성 증가 시점에 도입한다.

즉, 원칙은 다음과 같다.

- `Postgres = source of truth`
- `Redis = runtime acceleration layer`

### 13.5 Ops and Integration Automation

- `n8n`

역할:

- webhook intake
- schedule
- cross-tool sync
- alerts
- approval routing
- recurring workflows

최종 판단:

- 코어 브레인이 아니라 운영 자동화 레이어로 둔다.

### 13.6 Verification Stack

- `GitHub Actions`
- `Playwright`
- 프로젝트별 lint/typecheck/unit/integration 도구

### 13.7 MCP 우선순위

1. `GitHub MCP`
2. `Notion MCP`
3. `Playwright MCP`
4. `Slack MCP`
5. `Figma MCP`

## 14. 릴리즈에 대한 최종 판단

릴리즈는 존재하지만, v1에서는 `배포 자동화`보다 `배포 가능 상태 판정`에 초점을 둔다.

즉, v1에서 Release는 다음 의미를 가진다.

- changelog 정리
- release notes 초안 작성
- issue/PR 정합성 점검
- founder approval 기록
- 배포 가능 상태 판정

실제 배포 자동화는 v2 이후 반자동 또는 자동화 대상으로 확장한다.

## 15. 버전별 정의

### 15.1 v1: Personal Operator-Controlled Studio

정의:

- 창업자 통제 하에서 작동하는 최소 운영체계

핵심 구성:

- Manager
- PM
- Builder
- QA
- Postgres
- LangGraph
- n8n
- GitHub / Notion / Playwright 연동

핵심 특징:

- 요구사항부터 QA까지 한 사이클 실행 가능
- 상태 흐름과 산출물 규약 고정
- 승인 경계 수동 유지
- 릴리즈는 배포보다 판정 중심

v1 핵심 성공 기준:

- 한 개 기능 요청을 처음부터 끝까지 일관되게 처리할 수 있는가
- 산출물과 상태 기록이 남는가
- QA와 승인 경계가 실제로 동작하는가

### 15.2 v2: Business-Ready Repeatable System

정의:

- 반복 운영 가능한 비즈니스용 시스템

추가 요소:

- Builder를 Frontend / Backend로 분리
- Critic 추가
- Docs/Release 추가
- Redis 도입
- n8n queue mode 및 worker 구조 검토
- 승인 요청 자동화
- review comment 반영 루프
- 문서 동기화 자동화
- 운영 대시보드 강화
- 비용/우선순위/재시도 정책 강화

v2 핵심 성공 기준:

- 여러 작업을 안정적으로 반복 처리할 수 있는가
- 운영자의 개입이 필요한 구간이 명확한가
- 동시성 증가에도 시스템이 유지되는가

### 15.3 v3: Platform-Grade Multi-Project System

정의:

- 여러 프로젝트와 여러 사용자를 감당하는 플랫폼형 시스템

추가 요소:

- multi-project / multi-team 지원
- role-based access control
- policy-driven approval engine
- advanced queueing and scheduling
- agent runtime versioning
- deployment promotion and rollback
- advanced observability and audit
- knowledge accumulation loop

v3 핵심 성공 기준:

- 조직 단위 운영이 가능한가
- 정책, 권한, 승인, 감사가 체계화되었는가
- 플랫폼으로서 확장 가능한가

## 16. v1 개발 착수 범위

본 프로젝트는 보고서 작성 이후 바로 `v1 최소 운영체계` 구현으로 착수한다.

v1의 즉시 착수 범위는 다음과 같다.

### 16.1 문서 및 규약

- `docs/PRD.md` 템플릿
- `docs/ROADMAP.md` 템플릿
- `contracts/API_CONTRACT.yaml` 템플릿
- `docs/TEST_REPORT.md` 템플릿
- `docs/RELEASE_NOTES.md` 템플릿
- 산출물 연결 규칙 정의

### 16.2 상태 모델

- request state schema
- phase enum
- approval fields
- quality fields
- runtime fields

### 16.3 오케스트레이션 골격

- Manager -> PM -> Builder -> QA 흐름
- pause/resume 구조
- retry 및 escalation 규칙

### 16.4 외부 연동 최소셋

- GitHub 연동
- Notion 연동
- Playwright 기반 검증 연동
- n8n intake 및 알림 흐름

### 16.5 품질 게이트 최소셋

- lint
- typecheck
- unit
- smoke

### 16.6 관측성과 기록

- status logging
- heartbeat tracking
- execution event history
- blocker 기록

## 17. 리스크와 대응

### 17.1 과설계 위험

대응:

- v1은 역할과 인프라를 최소화한다.

### 17.2 책임 중복 위험

대응:

- LangGraph는 상태머신
- LangChain은 보조 계층
- n8n은 운영 자동화

### 17.3 운영 복잡도 증가 위험

대응:

- Postgres 중심으로 시작하고 Redis는 필요한 시점에만 편입한다.

### 17.4 품질 하락 위험

대응:

- QA와 품질 게이트를 중심 레이어로 둔다.

## 18. 최종 결론

본 프로젝트의 최종 결론은 다음과 같다.

1. `Agent Studio`는 비즈니스용 개인형 AI 개발 운영체계로 정의한다.
2. UX는 비동기 코딩 에이전트 방향을 따른다.
3. 실행 루프는 SWE 에이전트 패턴을 적극 활용한다.
4. 코어 오케스트레이션은 LangGraph 중심으로 설계한다.
5. 운영 자동화와 승인 연결은 n8n으로 분리한다.
6. 시스템 정본은 Postgres로 두고, Redis는 v2 이후 확장 레이어로 도입한다.
7. 프로세스는 `Stage-gated Agile`로 정의한다.
8. v1은 최소 운영체계, v2는 반복 운영체계, v3는 플랫폼 확장체계로 구분한다.

따라서 본 프로젝트는 단순한 AI 코딩 보조 도구를 넘어서, `1인 스튜디오가 실제 개발회사처럼 일할 수 있도록 만드는 구조적 운영 시스템`을 구축하는 것을 목표로 한다.
