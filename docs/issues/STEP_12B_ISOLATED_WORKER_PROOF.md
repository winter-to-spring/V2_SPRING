# [코어] Step 12-b - Isolated worker proof in sandbox/worktree

## 배경 / 문제

Routing policy만 있어서는 execution plane의 장점을 아직 얻지 못합니다.
다음 단계는 실제로 **single isolated worker**를 띄워,
bounded task 하나를 sandbox/worktree 안에서 수행하고 결과를 안전하게 회수하는
proof를 만드는 것입니다.

이 단계의 핵심은 worker가 빠르게 일하는 것이 아니라,
**메인 control plane을 오염시키지 않고도 isolated execution이 가능한가**를
증명하는 것입니다.

## 이번 단계의 목적

1. isolated worker를 단일 bounded task 기준으로 proof한다.
2. worker 실행이 sandbox/worktree 안에서만 일어나게 한다.
3. worker 결과를 `artifact / patch / receipt`로 회수한다.
4. timeout / cancel / orphan 가능성을 founder/operator가 볼 수 있게 한다.
5. 이후 더 빠른 bypass-style execution plane 확장의 안전한 기반을 만든다.

## 구현 범위

- single isolated worker adapter
- strengthened soft-isolation sandbox/worktree 준비
- isolation boundary rules
  - task-local working directory 강제
  - main repo 상위 경로 접근 금지
  - `.env` 및 local secrets 복사 금지
  - worker-visible env allowlist 또는 동등한 제한
  - ambient env 백지화 또는 최소 허용치만 전달
- bounded task 실행 proof
- output capture
  - patch/diff
  - artifacts
  - execution receipt
- timeout / cancellation / orphan-risk visibility
- synchronous hard timeout reclaim + timeout receipt
- CLI proof
  - 예: `v2-spring task dispatch <task-id> --runtime isolated_worker`
  - 또는 동등한 execution surface
- 관련 테스트 / docs / risk register 반영

## 이번 단계의 핵심 결정

1. **Main state는 worker가 직접 mutate하지 않음**
- worker는 patch/artifact/receipt만 반환합니다
- control plane이 intake 전까지 state transition을 확정하지 않습니다

2. **Single isolated worker proof first**
- 여러 worker를 병렬로 띄우지 않습니다
- 처음엔 한 번에 하나의 bounded worker만 proof합니다

3. **Cancellation은 "없던 일"이 아니라 receipt로 남김**
- local cancel이 일어나도 founder/operator가 orphan risk를 볼 수 있어야 합니다

4. **12-b는 강화된 Soft Isolation proof로 시작**
- 첫 proof는 Docker/E2B 같은 full container isolation까지 가지 않습니다
- 대신 `subprocess` + task-local working directory + env allowlist +
  `.env`/sensitive file 비복사 + bounded patch/artifact receipt 조합으로
  실행 평면 계약을 먼저 증명합니다
- 진짜 OS/container-level isolation 부재는 별도 리스크로 추적하고,
  unrestricted bypass worker를 넓게 열기 전 반드시 닫습니다

5. **조용한 죽음은 동기 timeout reclaim으로 회수**
- worker가 죽거나 멈추면 control plane이 무한 대기하지 않습니다
- 12-b에서는 `subprocess` 호출 경계에서 hard timeout을 걸고,
  timeout 시 즉시 process group을 정리한 뒤 `TimeoutReceipt`를 생성합니다
- 비동기 watchdog은 proof 이후 단계에서 필요해질 수 있지만,
  첫 proof에서는 blocking reclaim이 더 단순하고 결정론적입니다

## 이번 단계에서 하지 않는 것

- multi-worker orchestration
- distributed lease manager
- automatic patch apply
- multi-tenant sandbox fleet
- full OS/container-level isolation

## 리스크 게이트

- `RISK-0021` local CLI cancellation / provider orphan
- `RISK-0022` multi-worker approval concurrency

이번 단계에서의 처리:
- `RISK-0021`: isolated worker receipt와 cancellation/orphan visibility로 완화 또는 해결
- `RISK-0022`: 여전히 single-worker mode를 유지하여 범위를 제한
- `RISK-0023`: strengthened soft isolation의 최소 경계(task-local dir, env allowlist, secret 비복사)로 완화
- `RISK-0024`: silent worker crash / stuck running 상태를 synchronous hard timeout + timeout receipt로 다룸
- `RISK-0027`: OS/container-level isolation 부재는 새 리스크로 등록하고, unrestricted bypass worker 전까지 게이트로 유지

## Acceptance Criteria

- isolated worker가 bounded task 하나를 안전하게 수행할 수 있다
- worker output이 patch/artifact/receipt로 회수된다
- cancel/timeout 시 founder/operator가 orphan risk를 볼 수 있다
- worker crash / hard timeout이 silent failure가 아니라 timeout receipt로 회수된다
- worker는 task-local working directory와 env allowlist 경계 안에서만 실행된다
- `.env`와 local secret surface는 worker scope에 복사되지 않는다
- 12-b가 container isolation proof는 아니라는 점과, 그 결손이 별도 리스크로 남아 있다는 점이 문서에 명시된다
- replay에 isolated execution trail이 남는다
- main control plane state는 worker에 의해 직접 오염되지 않는다

## 연결 문서

- `docs/issues/STEP_12_EXECUTION_PLANE_EPIC.md`
- `docs/issues/STEP_12A_EXECUTION_PLANE_ROUTING_POLICY.md`
- `docs/risk-register/entries/2026-04-17-provider-cancellation-orphan.md`
- `docs/risk-register/entries/2026-04-17-multi-worker-approval-concurrency.md`
- `docs/risk-register/entries/2026-04-17-isolated-worker-sandbox-leakage.md`
- `docs/risk-register/entries/2026-04-17-silent-worker-crash-reclaim-gap.md`
- `docs/risk-register/entries/2026-04-17-lack-of-os-level-worker-isolation.md`
