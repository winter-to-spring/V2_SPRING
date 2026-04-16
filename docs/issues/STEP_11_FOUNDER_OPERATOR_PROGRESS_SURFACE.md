# [UI] Step 11 - Founder/operator progress surface + safe interaction ergonomics

## 배경 / 문제

Step 10까지 오면서 V2_SPRING은 planner/control-plane substrate를 꽤 단단하게
올렸습니다.

지금 founder는 CLI에서 다음을 확인할 수 있습니다.
- run / approval / replay / planner attempt / founder reply 흐름
- planner proposal legality와 governance 경계
- production transport seam과 bounded cancellation / retry 정책

하지만 아직 founder/operator 입장에서는 시스템이 **되는 것**과 **보이는 것**
사이에 간격이 남아 있습니다.

특히 지금 단계에서 바로 보완해야 할 두 가지 리스크가 있습니다.
- `RISK-0009`: planner-facing audit payload가 noisy하거나 unsafe해질 수 있음
- `RISK-0018`: founder reply CLI ergonomics가 나빠서 operator error를 유발할 수 있음

즉 Step 11은 단순한 UI polish가 아니라,
**founder/operator가 현재 상태, 막힘, 최근 개입, planner 흐름을 안전하고 짧게
이해하고 조작할 수 있는 progress surface**를 만드는 단계입니다.

## 이번 단계의 목적

1. founder/operator가 run 진행 상태를 한눈에 볼 수 있는 compact progress surface를 만든다.
2. planner / founder / approval / task / artifact 흐름을 읽기 쉬운 현재형 상태로 재구성한다.
3. noisy audit payload를 정돈해서 founder-facing surface에 올릴 수 있는 안전한 summary layer를 만든다.
4. founder reply ergonomics를 개선하여 `hint / override / reject` 입력 실수를 줄인다.
5. 이후 richer UI나 operator dashboard로 확장해도 typed contract는 그대로 재사용되게 한다.

## 구현 범위

- founder/operator progress summary read model
- compact status surface for:
  - run lifecycle
  - approval / timeout / suspended reason
  - latest planner attempt / escalation / founder intervention
  - latest bounded execution result
  - recent artifact headlines
- progress-oriented CLI surface 개선
  - current state 요약
  - blocked / waiting / suspended 이유
  - founder action entrypoint 단순화
- planner/audit payload sanitization and summarization layer
- founder reply command ergonomics 개선
  - enum-first, short-text contracts
  - malformed input / misuse 가드
  - `--hint-file` 같은 file-based input support 또는 동등한 multiline escape hatch
- pretty output + JSON output 병행
- 관련 ADR / implementation note / risk register 반영

## 이번 단계의 핵심 결정

1. **Progress summary는 materialized table이 아니라 on-the-fly projection**
- Step 11의 progress summary는 별도 write table로 유지하지 않습니다
- source of truth는 여전히 EventLedger와 현재 state tables입니다
- progress surface는 이 원본들을 fold/reduce한 read-only projection으로 계산합니다

2. **Compact summary와 raw escape hatch를 함께 제공**
- 기본 출력은 compact summary입니다
- 하지만 founder/operator가 디버깅이 필요할 때를 위해
  `--raw` 또는 `--trace` 같은 원본 열람 escape hatch를 제공합니다
- sanitization은 기본 surface에 적용하되, raw path는 명시적으로 선택해야 합니다

3. **Founder-facing 상태는 blocker 주체를 먼저 드러냄**
- 단순 `running` / `failed`보다
  `WAITING_ON_FOUNDER`, `WAITING_ON_APPROVAL`, `SUSPENDED_ON_TIMEOUT` 같은
  call-to-action 중심 상태를 우선 노출합니다
- founder가 "지금 내가 뭘 해야 하는가"를 첫 줄에서 알 수 있어야 합니다

4. **JSON 출력은 typed view model로 강제**
- JSON output은 ad-hoc dict dumping이 아니라
  `ProgressSummaryView` 같은 명시적 typed model을 거칩니다
- 이후 richer UI나 automation이 이 contract를 안정적으로 재사용할 수 있어야 합니다

5. **Founder reply ergonomics는 짧은 명령 + 파일 입력 탈출구 조합**
- 기본 경로는 짧은 enum + text 조합입니다
- 긴 multiline hint나 설정 조각은 `--hint-file` 또는 동등한 escape hatch를 둡니다
- founder가 shell escaping 지옥에 빠지지 않게 합니다

## 이번 단계에서 하지 않는 것

- full web UI or dashboard
- distributed worker orchestration
- multi-tenant auth / permissions
- execution workforce 확장 전체
- background planner workers
- materialized projection store

## 리스크 게이트

- `RISK-0009` planner-facing audit payload hygiene
- `RISK-0018` founder reply CLI ergonomics

추가로 주의할 점:
- founder-facing surface는 raw ledger를 그대로 노출하지 않고 summary layer를 거쳐야 합니다
- audit payload는 compact하고 stable error categories를 가져야 합니다
- founder reply surface는 긴 JSON 입력이 아니라 가능한 한 좁은 enum + text 조합으로 가야 합니다
- replay와 현재 상태 surface가 서로 모순되면 안 됩니다
- multiline founder hint는 file input 또는 동등한 편의 경로가 없으면 operator error를 유발합니다

## Acceptance Criteria

- founder/operator가 현재 run 상태를 한 화면에서 빠르게 파악할 수 있다
- blocked / waiting / suspended 이유가 compact하게 드러난다
- latest planner / founder / approval / execution 흐름이 읽기 쉬운 progress summary로 보인다
- founder reply CLI가 기존보다 짧고 오입력에 덜 취약하다
- multiline founder hint를 file-based path 또는 동등한 escape hatch로 입력할 수 있다
- planner-facing audit payload가 더 compact하고 safe한 summary 형태로 표면화된다
- raw/traced debugging을 위한 명시적 escape hatch가 존재한다
- JSON 출력이 typed view model을 거친다
- pretty / JSON 양쪽 출력이 존재한다
- replayable typed contract는 유지된다
- `RISK-0009`와 `RISK-0018`이 이 단계에서 명시적으로 완화 또는 해결된다

## 연결 문서

- `docs/adr/0005-founder-verification-surface.md`
- `docs/adr/0007-planner-decision-output-contract.md`
- `docs/implementation-notes/STEP_10B_FOUNDER_REPLY_CONTRACT.md`
- `docs/implementation-notes/STEP_10C_PRODUCTION_TRANSPORT_HARDENING.md`
- `docs/risk-register/entries/2026-04-16-planner-audit-payload-hygiene.md`
- `docs/risk-register/entries/2026-04-17-founder-reply-cli-ergonomics.md`
