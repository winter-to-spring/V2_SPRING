# [코어] Step 12-a - Execution plane routing policy + dispatch contract

## 배경 / 문제

Step 12의 첫 단계는 "worker를 붙이는 것"보다 먼저,
**control plane이 어떤 task를 어떤 execution runtime으로 보낼지 결정하는 규칙**을
정의하는 것입니다.

이 규칙이 없으면:
- bypass-style worker와 bounded executor가 뒤섞이고
- founder/operator는 왜 특정 runtime이 선택됐는지 설명을 못 듣고
- 나중에 CrewAI나 다른 execution runtime을 붙일 때 도메인 경계가 흐려집니다

즉 Step 12-a는 execution plane의 속도를 올리기 전에,
**routing policy와 dispatch contract를 먼저 typed하게 고정하는 단계**입니다.

## 이번 단계의 목적

1. execution runtime taxonomy를 정의한다.
2. planner-facing execution requirements contract를 정의한다.
3. task routing rule을 deterministic하게 만든다.
4. dispatch envelope / receipt contract를 typed model로 만든다.
5. dispatch 전 snapshot freshness guard를 명시한다.
6. founder/operator가 "왜 이 runtime이 선택됐는지" 추적할 수 있게 한다.

## 구현 범위

- `ExecutionRuntime` typed enum 또는 동등 모델
- planner-facing `ExecutionRequirements` typed model 또는 동등 계약
  - 예:
    - `task_complexity`
    - `needs_isolation`
    - `requires_network`
    - `needs_multi_file_context`
    - `write_scope`
    - `expected_output_kind`
- dispatcher sanity-check / normalization layer
  - obvious complexity over-estimation downgrade
  - suspicious requirement inflation rejection or cap
- max allowed capabilities policy
  - founder/system policy가 허용한 상한을 넘는 요구사항 거부
- unfulfillable route fallback path
  - matching runtime이 없을 때의 typed routing error / escalation 경로
- requirements -> runtime routing policy
- routing registry / policy table
- dispatch request / receipt typed contract
- dispatch base context contract
  - base run snapshot hash
  - base workspace/tree marker
  - per-file base hash 또는 동등한 conflict detection anchor
- routing rationale / capability match summary
- dispatch 전 legality / freshness guard
- CLI proof
  - 예: `v2-spring task route <run-id>`
  - 또는 동등한 inspection surface
- ADR / implementation note / risk register 반영

## 이번 단계의 핵심 결정

1. **Routing은 control plane 책임**
- worker가 자기 runtime을 고르지 않습니다
- planner는 런타임 이름을 직접 지시하지 않습니다
- planner는 작업의 요구사항(requirements)만 선언합니다
- control plane/dispatcher가 current state + requirements를 기준으로 runtime을 고릅니다

2. **Planner는 인프라를 몰라도 된다**
- planner output에는 `target_runtime=isolated_worker` 같은 하드코딩된 런타임 이름을 넣지 않습니다
- 이렇게 해야 provider/runtime taxonomy가 바뀌어도 planner prompt와 계약이 덜 흔들립니다

3. **지금은 최소 2개 runtime만 다룸**
- `bounded_local`
- `isolated_worker`
- future `CrewAI` runtime은 taxonomy에는 들어가되, 실제 dispatch proof는 뒤 단계에서 붙입니다

4. **Routing rule은 ad-hoc if/else가 아니라 registry로 관리**
- 첫 구현은 점수 기반 scoring registry가 아니라
  **눈에 보이는 명시적 rule branches / policy functions**로 시작합니다
- 대신 giant if/elif monster를 키우지 않도록
  runtime capability와 planner requirements를 매핑하는 좁은 policy table + named guards를 둡니다

5. **Planner requirements는 힌트이지 권한이 아니다**
- dispatcher는 planner가 요청한 complexity / capability를 그대로 믿지 않습니다
- obvious over-estimation은 downshift할 수 있어야 합니다
- founder/system policy가 허용한 상한을 넘는 capability 요구는 reject 또는 escalation 합니다

6. **Unfulfillable route는 조용히 fallback하지 않는다**
- 현재 등록된 runtime 중 조건을 만족하는 것이 없으면 typed routing error를 반환합니다
- 필요한 경우 founder-visible escalation로 연결되지만, 무의미한 hidden fallback은 하지 않습니다

7. **Freshness guard가 dispatch 앞단에 있어야 함**
- stale snapshot을 믿고 isolated worker를 띄우지 않습니다
- dispatch 직전에 state hash / current blocker를 다시 확인합니다

8. **Dispatch receipt는 나중 intake conflict를 설명할 수 있어야 함**
- worker가 어떤 코드 상태를 기준으로 작업을 시작했는지 base context가 남아야 합니다
- 이후 patch intake 시 현재 워크트리와 base hash가 다르면
  safe rejection path로 되돌리고 planner에 conflict-aware failure report를 줍니다

## 이번 단계에서 하지 않는 것

- actual multi-worker fan-out
- distributed queue / lease orchestration
- full CrewAI runtime integration
- patch apply / merge gate

## 리스크 게이트

- `RISK-0005` run snapshot staleness under concurrent writes
- `RISK-0022` multi-worker approval concurrency

이번 단계에서의 처리:
- `RISK-0005`: dispatch freshness guard + base file hash / safe rejection path로 완화 또는 해결
- `RISK-0022`: 이번 단계에서는 multi-worker를 열지 않음으로써 범위를 제한
- runtime naming leakage / hallucinated routing은 requirements-based dispatch로 예방
- complexity over-estimation / privilege escalation / unfulfillable route는 dispatcher sanity-check와 typed routing refusal로 처리

## Acceptance Criteria

- execution runtime taxonomy가 typed contract로 존재한다
- planner-facing execution requirements contract가 typed model로 존재한다
- task routing이 requirements -> runtime deterministic rule로 계산된다
- dispatcher가 obvious over-estimation을 downshift하거나 reject할 수 있다
- dispatcher가 founder/system max capability policy를 넘는 요구를 reject 또는 escalation 할 수 있다
- matching runtime이 없을 때 typed routing error 또는 founder-visible escalation 경로가 존재한다
- dispatch 전에 freshness/legality guard가 실행된다
- founder/operator가 routing decision과 rationale을 CLI에서 확인할 수 있다
- planner output에 provider/runtime 이름이 직접 노출되지 않는다
- stale dispatch 시도는 명시적 에러 또는 safe refusal로 거부된다
- dispatch receipt에 later intake conflict를 설명할 수 있는 base context가 남는다
- base context가 달라진 worker output은 safe rejection path로 되돌릴 수 있다
- replay에 routing decision trail이 남는다

## 연결 문서

- `docs/issues/STEP_12_EXECUTION_PLANE_EPIC.md`
- `docs/adr/0004-deterministic-substrate.md`
- `docs/risk-register/entries/2026-04-16-run-snapshot-staleness.md`
- `docs/risk-register/entries/2026-04-17-multi-worker-approval-concurrency.md`
- `docs/risk-register/entries/2026-04-17-routing-policy-sprawl.md`
