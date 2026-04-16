# [코어] Step 9 - Bounded replanning loop + planner attempt governance

## 배경 / 문제

Step 8까지 오면서 V2_SPRING은 planner proposal의 legality와 freshness를
검증할 수 있게 됐습니다.

하지만 아직 시스템은 다음 질문에 대한 공식 답이 없었습니다.

- stale proposal을 몇 번까지 봐줄 것인가
- illegal proposal이 반복되면 언제 멈출 것인가
- 중복 proposal은 어떤 기준으로 구분할 것인가
- founder는 언제, 어떤 방식으로 exhausted 상태를 다시 열 수 있는가

이 규칙이 없으면 real planner adapter를 붙이는 순간 시스템은
"실패는 맞게 하지만 무한히 반복되는" 상태로 빠질 수 있습니다.

## 이번 단계의 목적

이번 단계는 planner를 더 똑똑하게 만드는 것이 아니라,
planner가 bounded하게 실패하고 bounded하게 다시 시도하도록 만드는
거버넌스 경계를 고정하는 데 목적이 있습니다.

핵심 목표는 아래와 같습니다.

1. phase-scoped planner budget을 도입한다
2. planner attempt를 append-only로 남긴다
3. stale / illegal / duplicate / exhausted를 구조화된 outcome으로 관리한다
4. founder가 manual recharge로 exhausted phase를 다시 열 수 있게 한다
5. replay에서 planner failure와 recharge 흔적을 읽을 수 있게 한다

## 구현 범위

- typed `PlannerAttempt` / `PlannerGovernance` 모델
- phase budget / exhaustion 정책
- transport duplicate / cognitive duplicate 1차 정책
- `planner recharge` CLI
- `planner attempts` CLI
- replay에 planner governance 요약 추가
- Step 9 ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- 실제 LangGraph adapter 연결
- semantic duplicate의 고급 판별
- distributed lock
- automatic planner chaining
- founder UI

## Acceptance Criteria

- stale / illegal / duplicate proposal이 구조화된 attempt outcome으로 남는다
- planner phase budget이 bounded하게 감소한다
- budget 소진 시 `phase_exhausted`가 append-only로 기록된다
- founder가 `planner recharge`로 exhausted phase를 다시 열 수 있다
- recharge 후 새 proposal이 legal guard를 다시 통과할 수 있다
- replay에서 planner attempts 요약을 읽을 수 있다
- 테스트가 통과한다

## 연결 문서

- `docs/adr/0006-bounded-replanning-governance.md`
- `docs/implementation-notes/STEP_9_BOUNDED_REPLANNING_AND_PLANNER_GOVERNANCE.md`
- `docs/risk-register/entries/2026-04-16-planner-proposal-loop-control.md`
