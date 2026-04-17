# [코어] Step 12 Epic - Execution plane routing and isolated worker proof

## 배경 / 문제

Step 11까지 오면서 V2_SPRING은 planner/control-plane substrate와
founder/operator progress surface를 꽤 단단하게 올렸습니다.

지금 시스템은 다음을 이미 갖추고 있습니다.
- typed state + immutable ledger
- approval / founder intervention / planner governance
- replayable progress surface
- production planner transport seam

하지만 아직 execution plane은 비교적 단순합니다.
지금의 bounded executor는 "control plane이 안전하다"는 것을 증명하는 데에는 충분했지만,
앞으로 우리가 원하는 더 빠른 실행 경로를 열기에는 부족합니다.

우리가 장기적으로 원하는 구조는 다음입니다.
- 머리: V2_SPRING control plane / planner / governance
- 손발: task 성격에 따라 분기되는 execution runtimes
  - bounded local executor
  - future CrewAI team
  - isolated bypass-style worker

즉 Step 12는 단순히 worker를 더 붙이는 단계가 아니라,
**어떤 task를 어떤 execution plane으로 보낼지 정하고, 그 결과를 안전하게 다시
control plane으로 회수하는 계약과 proof path**를 여는 단계입니다.

## 이번 에픽의 목적

1. execution plane routing policy를 명확히 정의한다.
2. planner가 runtime 이름이 아니라 execution requirements를 선언하게 한다.
3. control plane이 그 requirements를 기준으로 execution runtime을 선택할 수 있게 한다.
4. isolated worker를 단일 bounded task 수준에서 안전하게 proof한다.
5. worker 결과를 `artifact / patch / receipt` 형태로 회수하는 intake path를 만든다.
6. founder가 실행 결과를 review/approve/reject 할 수 있는 gate를 붙인다.

## 에픽 분해

### Step 12-a
**Execution plane routing policy + dispatch contract**

- execution runtime taxonomy
- planner-facing execution requirements
- routing rules
- dispatch envelope / receipt contract
- freshness guard

### Step 12-b
**Isolated worker proof**

- single isolated worker path
- bounded sandbox/worktree execution
- patch/artifact/receipt capture
- timeout/cancel/orphan visibility

### Step 12-c
**Patch intake / founder review gate**

- worker output intake
- compact review surface
- founder approve/reject gate
- replayable merge/apply trail

## 이번 에픽의 핵심 결정

1. **Control plane은 하나, execution runtime은 여러 개**
- 어떤 runtime을 사용할지는 worker가 아니라 control plane이 결정합니다
- execution plane은 adapter처럼 연결됩니다

2. **Planner는 요구사항을 말하고, dispatcher가 runtime을 고른다**
- planner가 `isolated_worker` 같은 concrete runtime 이름을 직접 고르지 않습니다
- planner는 complexity / isolation / network / context width 같은 requirements를 선언합니다
- dispatcher가 가장 적합하고 가장 싼 runtime으로 매핑합니다

3. **Dispatcher는 요구사항을 그대로 믿지 않는 수문장**
- planner requirements는 힌트이지 권한 자체가 아닙니다
- dispatcher는 over-estimation, privilege escalation, unfulfillable route를 검사합니다
- founder/system policy가 허용한 capability 상한도 dispatcher가 강제합니다

4. **Single-worker proof first**
- 처음부터 multi-worker를 열지 않습니다
- isolated worker 한 명이 bounded task를 수행하는 최소 proof부터 갑니다

5. **Result는 patch/artifact/receipt로만 회수**
- worker는 메인 control plane state를 직접 mutate하지 않습니다
- 결과는 patch/diff/artifact/receipt 형태로만 회수합니다

6. **Founder review는 execution 이후 gate로 유지**
- worker가 빠르더라도 최종 intake/apply는 founder review 가능 상태로 남깁니다

## 리스크 게이트

- `RISK-0005` run snapshot staleness under concurrent writes
- `RISK-0021` local CLI cancellation / provider orphan
- `RISK-0022` multi-worker approval concurrency

이번 에픽에서의 접근:
- `RISK-0005`는 dispatch freshness guard로 먼저 완화
- `RISK-0021`은 isolated worker proof에 cancellation/orphan receipt를 명시
- `RISK-0022`는 이번엔 multi-worker를 열지 않음으로써 범위를 제한하고,
  남는 scale 문제는 계속 `Before Scale`로 유지

## Acceptance Criteria

- control plane이 task를 execution runtime으로 라우팅할 수 있다
- isolated worker proof가 bounded task 기준으로 동작한다
- worker output이 artifact / patch / receipt로 회수된다
- founder/operator가 worker output을 review할 수 있다
- apply/reject 흐름이 replay 가능한 ledger trail로 남는다
- `RISK-0005`, `RISK-0021`, `RISK-0022`가 각 서브 스텝에서 명시적으로 다뤄진다

## 연결 문서

- `docs/charter/FINAL_DIRECTION.md`
- `docs/adr/0004-deterministic-substrate.md`
- `docs/adr/0006-bounded-replanning-governance.md`
- `docs/adr/0009-production-planner-transport-seam.md`
- `docs/implementation-notes/STEP_10C_PRODUCTION_TRANSPORT_HARDENING.md`
- `docs/implementation-notes/STEP_11_FOUNDER_OPERATOR_PROGRESS_SURFACE.md`
- `docs/risk-register/entries/2026-04-16-run-snapshot-staleness.md`
- `docs/risk-register/entries/2026-04-17-provider-cancellation-orphan.md`
- `docs/risk-register/entries/2026-04-17-multi-worker-approval-concurrency.md`
