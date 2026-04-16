# Agent Studio 제출용 기획보고서

Updated: 2026-04-10 (Asia/Seoul)

## 1. 보고서 목적

본 보고서는 `개인형 AI 개발 스튜디오` 구축을 위한 기획 방향을 정리한 제출용 문서이다.

본 프로젝트는 단순한 코딩 보조 도구를 만드는 것이 아니라, 실제 비즈니스 환경에서 사용할 수 있는 `AI 기반 개발 운영체계`를 만드는 것을 목표로 한다. 즉, 아이디어와 요구사항을 입력으로 받아 PRD 작성, 계획 수립, 작업 분해, 구현, 검증, 문서화, 승인까지 이어지는 전 과정을 구조화하고, 그 과정 전체를 AI 에이전트와 워크플로우 중심으로 운영하는 시스템을 설계하는 것이 목적이다.

이 문서는 다음 질문에 답하도록 구성하였다.

- 우리는 무엇을 만들려고 하는가
- 어떤 방향들을 검토했는가
- 어떤 기준으로 비교했는가
- 최종적으로 어떤 구조로 가기로 했는가
- 해당 구조의 핵심 특징과 기술 스택은 무엇인가
- 버전별로 어떻게 확장할 것인가

## 2. 프로젝트 배경과 최종 목표

### 2.1 배경

기존의 일반적인 AI 코딩 도구는 대체로 단일 작업 단위의 보조에 집중되어 있다. 예를 들어 코드 생성, 테스트 생성, 일부 리팩토링, 문서 초안 작성 등에는 유용하지만, 실제 비즈니스 운영에 필요한 다음 요소들은 상대적으로 약하다.

- 요구사항과 기술계획의 연결
- 역할 분리와 책임 분리
- 품질 게이트와 승인 경계
- 상태 추적과 재시도 정책
- 문서, 이슈, 코드, 검증 결과의 일관된 연결
- 릴리즈 전후 운영 흔적과 감사성

본 프로젝트는 이러한 한계를 보완해, `1인 개발 스튜디오가 AI 팀을 거느린 것처럼 운영되는 체계`를 구축하는 것을 목표로 한다.

### 2.2 최종 목표

최종 목표는 다음과 같다.

1. 아이디어 또는 요구사항을 입력으로 받는다.
2. 이를 PRD, 기술계획, 작업 단위로 구조화한다.
3. 역할이 분리된 AI 에이전트들이 구현과 검증을 수행한다.
4. 모든 작업은 상태, 로그, 산출물, 승인 기록을 남긴다.
5. 위험이 큰 경계에서는 반드시 사람 승인을 요구한다.
6. 최종적으로는 실제 비즈니스 운영에 투입 가능한 `AI 개발 운영 시스템`으로 확장한다.

이 시스템은 `완전 자율 회사`를 지향하지 않는다. 오히려 창업자 또는 운영자가 최종 판단권을 가지면서도, 실행과 반복 업무는 AI가 맡는 형태를 지향한다.

## 3. 검토한 방향과 비교 관점

본 프로젝트의 방향을 정하기 위해 다음 다섯 가지 축을 기준으로 벤치마킹과 구조 비교를 진행하였다.

### 3.1 제품형 비동기 코딩 에이전트

검토 이유:

- 실제 사용자 관점에서 가장 직관적인 형태이기 때문
- 작업을 백그라운드로 보낸 뒤 상태를 추적하고 결과를 받는 UX가 비즈니스용 운영에 적합하기 때문

참고한 핵심 특징:

- 비동기 작업 실행
- 상태 표시와 로그 추적
- 브랜치, PR, 리뷰, 재수정 루프
- 사람 승인 후 다음 단계 진행

평가:

- 장점은 제품 경험이 명확하다는 점이다.
- 단점은 겉모습만 따라가면 내부 운영 로직이 약해질 수 있다는 점이다.

결론:

- `사용자 경험의 방향성`은 제품형 비동기 에이전트에서 가져간다.
- 다만 내부 실행 로직은 별도의 오케스트레이션 설계가 필요하다.

### 3.2 오픈소스 SWE 에이전트

검토 이유:

- 실제 코드 수정, 테스트 실행, 이슈 해결 루프에 강하기 때문
- 구현과 검증 루프를 설계하는 데 직접적인 참고가 되기 때문

참고한 핵심 특징:

- issue-to-fix 루프
- tool use 기반 작업
- 실행 결과 중심의 판정
- 테스트 및 검증 기반 반복 수정

평가:

- 장점은 실무형 실행 패턴을 가져오기 좋다는 점이다.
- 단점은 제품 운영, 승인, 문서, 거버넌스 레이어까지는 직접 채워 넣어야 한다는 점이다.

결론:

- `실행 엔진의 행동 패턴`은 오픈소스 SWE 에이전트에서 참고한다.
- 그러나 최종 시스템은 SWE agent 그 자체가 아니라, SWE agent를 품은 운영 플랫폼으로 간다.

### 3.3 멀티에이전트 오케스트레이션

검토 이유:

- 역할 분리, 상태 관리, 재시도, 승인 중단, resume가 필요하기 때문
- 단일 프롬프트 기반 자동화로는 비즈니스용 운영체계를 만들기 어렵기 때문

비교 포인트:

- `LangGraph` 중심 구조
- `LangChain` 중심 고수준 조합 구조
- `n8n` 중심 에이전트 워크플로우 구조

평가:

- `LangGraph`는 long-running, stateful workflow와 human-in-the-loop에 강하다.
- `LangChain`은 상위 추상화로 유용하지만, 코어 상태머신 자체를 맡기기에는 오히려 중첩 추상화가 늘어날 수 있다.
- `n8n`은 트리거, 알림, 외부 연결에는 뛰어나지만 코어 에이전트 상태머신 전체를 맡기기에는 운영 로직이 분산될 가능성이 있다.

결론:

- `LangGraph 중심`으로 간다.
- `LangChain`은 필요한 범위에서만 얇게 사용한다.
- `n8n`은 코어 브레인이 아니라 운영 자동화 레이어로 사용한다.

### 3.4 운영/승인 레이어

검토 이유:

- 실제 비즈니스 운영에서는 단지 코드가 생성되는 것보다 승인, 알림, 동기화, 반복 작업 관리가 중요하기 때문

비교 포인트:

- 모든 외부 연동을 애플리케이션 코드로 직접 작성
- 운영 자동화는 `n8n`으로 분리

평가:

- 모든 외부 연동을 직접 코드로 작성하면 시스템 표면적과 유지보수 비용이 빠르게 증가한다.
- `n8n`을 사용하면 웹훅, 스케줄, 알림, GitHub/Notion 동기화 등 저위험 운영 자동화를 별도 레이어로 분리할 수 있다.

결론:

- 운영 자동화와 승인 요청, 문서/이슈 동기화는 `n8n`이 맡는다.
- 핵심 상태 전이와 판단은 `LangGraph`가 맡는다.

### 3.5 평가/리서치 기준

검토 이유:

- 비즈니스용 시스템은 단순 생성 성능보다 신뢰 가능한 운영 성능이 중요하기 때문

비교 포인트:

- 모델의 코딩 성능
- 작업 성공률
- 테스트 통과율
- 재시도 효율
- 승인 전 품질 수준
- 운영 지표 추적 가능성

결론:

- 단순 벤치마크 점수보다 `실행 성공률, 품질 게이트 통과율, 승인 필요 비율, 실패 복구율` 같은 운영 KPI를 우선시한다.
- 즉, 연구용 평가체계를 참고하되 비즈니스용 평가 프레임으로 재구성한다.

## 4. 주요 선택지와 최종 결정

### 4.1 프로세스 방식: Waterfall vs Agile

검토 내용:

- 순차적 문서 중심의 `Waterfall`
- 반복적 구현과 검증 중심의 `Agile`

최종 결정:

- `Stage-gated Agile`로 간다.

결정 이유:

- 요구사항 승인, 보안, 데이터 삭제, 배포 같은 고위험 구간은 게이트가 필요하다.
- 동시에 구현과 검증은 짧은 반복 루프가 더 적합하다.
- 따라서 앞단은 구조화하고, 중간은 반복적으로 실행하며, 뒤쪽은 승인 기반으로 통제하는 방식이 적절하다.

정리하면 다음과 같다.

- 요구사항과 계획은 비교적 엄격하게 구조화
- 구현과 수정은 반복형으로 운영
- 최종 외부 반영은 승인 게이트로 관리

### 4.2 오케스트레이션 중심: LangGraph vs LangChain 중심 vs n8n 중심

최종 결정:

- `LangGraph 중심`

결정 이유:

- 상태 전이와 long-running workflow를 코어에서 다루기 좋다.
- human-in-the-loop와 durable execution이 핵심 요구사항에 맞는다.
- agent 수가 늘어나도 역할과 단계를 구조화하기 쉽다.

보조 결정:

- `LangChain`은 툴 바인딩, 모델 추상화, 일부 유틸 수준으로 최소 사용
- `n8n`은 운영 자동화 레이어로 한정

### 4.3 상태 저장과 분산 운영: Postgres vs Redis vs 병행 구조

최종 결정:

- `v1은 Postgres 중심`
- `v2부터 Redis 추가 가능`

결정 이유:

- 최종 상태, 승인 기록, 실행 메타데이터, 감사 로그는 `Postgres`가 정본이어야 한다.
- `Redis`는 고속 큐, 캐시, Pub/Sub, lock, idempotency, heartbeat freshness 검증에 적합하다.
- 그러나 초기 단계부터 Redis까지 강하게 의존하면 운영 복잡도가 증가한다.

따라서 다음 원칙을 채택한다.

- `Postgres`는 source of truth
- `Redis`는 ephemeral runtime utility
- `v1`은 Redis 없이도 설계 가능하게 구성
- `v2`에서 queue mode, worker 분리, 고동시성 요구가 생기면 Redis 도입

### 4.4 GitHub / Notion / n8n의 역할 분담

최종 결정:

- `GitHub`는 실행의 정본
- `Notion`은 비즈니스 컨텍스트의 정본
- `n8n`은 연결과 자동화의 정본

분담 기준:

- GitHub: Issues, Branches, PR, Reviews, Releases
- Notion: Product Inbox, PRD, Roadmap overview, Decision logs, Runbooks
- n8n: Intake, Sync, Alerts, Recurring jobs, Approval routing

이 분담을 통해 각 도구의 강점을 살리면서 중복 운영을 줄이는 방향을 선택하였다.

### 4.5 릴리즈 자동화 시점

최종 결정:

- `v1에서는 배포 자동화를 핵심 범위에서 제외`
- `v2 이후에 반자동 또는 자동화 대상으로 편입`

결정 이유:

- 현재 우선순위는 "배포"보다 "배포 가능 상태를 신뢰성 있게 판정하는 구조"를 만드는 것이다.
- 즉, 지금 필요한 것은 릴리즈 파이프라인보다 `완료 판정`, `QA 결과`, `승인 경계`, `문서 패키징`이다.

따라서 v1의 Release는 `배포`가 아니라 다음 의미로 정의한다.

- changelog 정리
- release note 초안 작성
- issue/PR 연결 상태 점검
- founder approval 기록
- 배포 가능한 상태 판정

## 5. 최종 방향성

본 프로젝트의 최종 방향은 다음과 같이 정의한다.

`제품형 비동기 코딩 에이전트의 UX`와
`오픈소스 SWE 에이전트의 실행 루프`와
`LangGraph 중심의 멀티에이전트 오케스트레이션`과
`n8n 기반 운영/승인 자동화`를 결합한
`비즈니스용 개인형 AI 개발 운영체계`를 구축한다.

즉, 이 시스템은 다음 네 가지를 동시에 만족해야 한다.

1. 실제로 구현과 검증이 가능해야 한다.
2. 사람이 상태와 진행 상황을 이해할 수 있어야 한다.
3. 고위험 경계에서는 반드시 승인이 걸려야 한다.
4. 버전 업과 팀 확장을 고려해 레이어형 구조로 설계되어야 한다.

## 6. 핵심 특징

### 6.1 워크플로우 중심 운영

- 에이전트는 자유 대화형이 아니라 상태머신 기반으로 동작한다.
- 각 작업은 `요청 -> 계획 -> 분해 -> 구현 -> 검증 -> 승인` 흐름을 따른다.

### 6.2 아티팩트 중심 커뮤니케이션

- 채팅이 아니라 문서, 이슈, 계약서, 리포트, PR이 중심이 된다.
- 모든 중요한 단계는 산출물로 남겨 추적 가능해야 한다.

### 6.3 품질 게이트 중심 검증

- `Tests before trust` 원칙을 채택한다.
- 코드가 생성되었다는 사실만으로 완료로 보지 않는다.
- lint, typecheck, unit, smoke, integration, E2E 등을 단계별 게이트로 적용한다.

### 6.4 승인 경계 기반 거버넌스

- 요구사항 최종 확정
- 외부 동작 변경
- 보안, 권한, 결제, 데이터 삭제
- 프로덕션 배포

위 영역은 자동 완료 대상이 아니라 반드시 사람 확인이 필요한 구간으로 정의한다.

### 6.5 역할 분리

- Manager: 라우팅 및 상태 관리
- PM: PRD와 요구사항 정리
- Builder 또는 FE/BE: 구현
- Critic: 리스크 리뷰
- QA: 검증 및 게이트 집행
- Docs/Release: changelog, release note, 문서 동기화

### 6.6 관측 가능성

- 현재 단계
- 현재 담당 에이전트
- 마지막 heartbeat
- 실패 원인
- 재시도 횟수
- 승인 대기 상태

위 상태를 추적할 수 있도록 설계한다.

## 7. 계층형 아키텍처

본 프로젝트는 다음과 같은 레이어로 설계한다.

### 7.1 Business Layer

- 어떤 영역을 자동화할지 정의
- 어디서 사람 승인을 넣을지 정의
- 비즈니스 리스크 경계를 규정

### 7.2 Workflow Layer

- 요청의 단계 흐름을 정의
- 상태 전이 규칙과 실패 처리 규칙을 정의

### 7.3 Agent Layer

- 역할별 에이전트 책임 분리
- 허용 도구와 쓰기 범위를 제한

### 7.4 Execution Layer

- LangGraph 기반 orchestration
- retry, pause, resume, escalation 처리

### 7.5 Integration Layer

- GitHub, Notion, Slack, Playwright, Figma, n8n 연결

### 7.6 State Layer

- Postgres 기반 정본 저장
- Redis 기반 runtime utility 확장

### 7.7 Quality Layer

- 테스트, 계약 검증, 모듈 검증, 통합 검증, 승인 전 검사

### 7.8 Observability Layer

- heartbeat, status, event history, failure logs, dashboard data

## 8. 기술 스택 결정안

### 8.1 Core Orchestration

- `LangGraph`

역할:

- 에이전트 흐름 제어
- 상태 전이 관리
- pause/resume
- human approval 경계 처리
- critic-revision-qa 루프 제어

선정 이유:

- 장기 실행과 상태 기반 분기가 핵심 요구사항에 적합함

### 8.2 Agent Utility Layer

- `LangChain` 최소 사용

역할:

- 모델 바인딩
- 일부 도구 연결 추상화
- 보조 유틸리티

선정 이유:

- 코어 오케스트레이션을 담당시키지 않고 필요한 부분만 사용해 복잡도 증가를 막기 위함

### 8.3 State and Audit

- `Postgres` 또는 `Supabase`

역할:

- request state
- execution metadata
- approvals
- audit history
- dashboard source data

선정 이유:

- 정합성과 감사성, 비즈니스 데이터 정본 역할에 적합함

### 8.4 Queue / Cache / Realtime Utility

- `Redis` (v2 이후 점진 도입)

역할:

- ephemeral queue
- cache
- Pub/Sub
- distributed lock
- idempotency helper
- heartbeat freshness

선정 이유:

- 비즈니스 확장 시 반드시 유용하지만, v1에서 필수 인프라는 아님

### 8.5 Ops and Automation

- `n8n`

역할:

- webhook intake
- schedule
- alerts
- GitHub/Notion sync
- approval request routing
- recurring jobs

선정 이유:

- 외부 연결과 저위험 운영 자동화를 별도 레이어로 분리하기 좋음

### 8.6 External Tool Access

- `MCP`

우선순위:

1. GitHub MCP
2. Notion MCP
3. Playwright MCP
4. Slack MCP
5. Figma MCP

선정 이유:

- 외부 도구 접근 규칙을 일관되게 유지할 수 있음

### 8.7 Verification and QA

- `GitHub Actions`
- `Playwright`
- 프로젝트별 lint/typecheck/unit/integration 도구

역할:

- 자동 검증
- 통합 검증
- 실행 기반 품질 판단

## 9. SDLC 반영 방향

본 시스템은 SDLC를 다음 단계로 반영한다.

1. 요구사항 수집
2. PRD 작성 및 승인
3. 기술 계획 수립
4. 작업 분해
5. 구현
6. 리뷰 및 비평
7. QA 검증
8. 문서 정리
9. 승인 대기
10. 완료 또는 릴리즈 준비

이 구조는 순수 Waterfall이 아니라 `Agile delivery + gated governance` 방식이다.

즉:

- 앞단은 명세와 승인 중심
- 중간은 반복 구현과 검증 중심
- 뒷단은 승인과 통제 중심

## 10. QA와 승인 구조

### 10.1 QA의 위치

QA는 단순 마지막 테스트 담당이 아니라 전체 흐름의 핵심 제어축이다.

QA는 최소 세 단계에 개입한다.

1. `Task QA`
   개별 구현 단위 검증
2. `Merge QA`
   통합 전후 검증
3. `Release QA`
   승인 직전 최종 상태 점검

### 10.2 품질 게이트

#### Module Gate

- lint
- typecheck
- unit test
- module smoke test
- contract conformance

#### Integration Gate

- application boot
- env validation
- migration verification
- API health check
- integration scenarios
- Playwright happy path

#### Release Gate

- changelog updated
- release notes drafted
- linked issue and PR status complete
- founder approval recorded

### 10.3 사람 승인 필수 구간

- final PRD approval
- pricing, billing, auth, security, external behavior 변화
- destructive DB change
- production release
- data deletion
- secrets or permission change
- external communication

## 11. 버전별 정의

### 11.1 v1: Personal Operator-Controlled Studio

정의:

- 창업자 통제 하에서 작동하는 최소 운영체계

구성:

- Manager
- PM
- Builder
- QA

기술 스택:

- Postgres
- LangGraph
- n8n
- GitHub MCP
- Notion MCP
- Playwright MCP

특징:

- 상태 흐름 고정
- PRD, ROADMAP, TEST_REPORT 등 산출물 규약 확립
- 최소 품질 게이트 적용
- 승인 경계 수동 유지
- 릴리즈는 배포 자동화보다 `배포 가능 상태 판정`에 집중

목표:

- 실제로 한 사이클을 끝까지 굴릴 수 있는지 검증

### 11.2 v2: Business-Ready Repeatable System

정의:

- 반복 운영 가능한 비즈니스용 시스템

추가 요소:

- Builder를 FE / BE로 분리
- Critic 추가
- Docs/Release 추가
- Redis 도입 가능
- n8n queue mode 및 worker 분리 검토
- review comment 반영 루프
- 승인 요청 자동화
- 문서 동기화 자동화
- 운영 대시보드 강화
- 비용, 우선순위, 재시도 정책 정교화

목표:

- 한 번 작동하는 수준을 넘어 반복 가능성과 운영성을 확보

### 11.3 v3: Platform-Grade Multi-Project System

정의:

- 여러 프로젝트와 여러 사용자를 감당하는 플랫폼형 시스템

추가 요소:

- multi-project / multi-team 구조
- 역할 기반 권한관리
- policy-driven approval engine
- agent runtime versioning
- advanced queueing and scheduling
- 감사, 보안, 운영 지표 고도화
- staged deployment and rollback
- knowledge accumulation and learning loop

목표:

- AI가 개발을 돕는 수준을 넘어, AI 개발조직 운영 플랫폼으로 확장

## 12. 기대 효과

### 12.1 실행력 향상

- 기획부터 구현, 검증, 문서화까지 이어지는 연속 흐름 확보

### 12.2 운영 일관성 확보

- 모든 작업이 산출물과 상태 기록을 남기므로 반복성과 추적성이 증가

### 12.3 품질 통제 가능

- 검증 없는 완료를 허용하지 않음으로써 신뢰성을 확보

### 12.4 1인 운영의 확장성

- 실제 조직을 만들기 전에도 역할 분리형 운영 체계를 확보 가능

### 12.5 향후 확장 용이

- v1에서 시작하더라도 v2, v3로 자연스럽게 확장 가능한 레이어형 구조 확보

## 13. 주요 리스크와 대응 방향

### 13.1 초기 과설계 위험

리스크:

- 시작 단계에서 너무 많은 역할과 시스템을 동시에 도입할 가능성

대응:

- v1은 Manager, PM, Builder, QA만으로 시작

### 13.2 도구 중복 위험

리스크:

- LangGraph, LangChain, n8n의 책임이 겹칠 수 있음

대응:

- LangGraph는 코어 상태머신
- LangChain은 최소 보조
- n8n은 외부 운영 자동화

### 13.3 운영 복잡도 증가 위험

리스크:

- Redis, worker, dashboard, queue가 너무 빨리 들어오면 유지보수 비용이 커짐

대응:

- Postgres 중심으로 시작하고 Redis는 필요 시점에 단계적으로 편입

### 13.4 품질 통제 실패 위험

리스크:

- 코드 생성량은 늘지만 실제 품질이 떨어질 수 있음

대응:

- QA와 명시적 품질 게이트를 시스템의 중심에 둠

## 14. 최종 결론

본 프로젝트는 `AI가 코드를 작성해주는 도구`가 아니라 `비즈니스용 AI 개발 운영체계`를 만드는 프로젝트로 정의한다.

검토 결과, 최종 방향은 다음과 같이 확정한다.

1. 제품 경험은 `비동기 코딩 에이전트` 방향을 따른다.
2. 실행 루프는 `오픈소스 SWE 에이전트` 패턴을 참고한다.
3. 코어 오케스트레이션은 `LangGraph 중심`으로 설계한다.
4. 운영 자동화와 승인 연결은 `n8n`으로 분리한다.
5. 데이터 정본은 `Postgres`로 두고, `Redis`는 v2 이후 운영 확장 시 도입한다.
6. 프로세스는 `Stage-gated Agile`로 정의한다.
7. v1은 최소 운영체계, v2는 비즈니스 반복 운영체계, v3는 플랫폼형 확장체계로 나눈다.

따라서 본 기획의 핵심은 단순한 멀티에이전트 시연이 아니라, `1인 스튜디오가 실제 개발회사처럼 운영되도록 만드는 구조적 시스템 설계`에 있다.
