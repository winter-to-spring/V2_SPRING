# [코어] Step 17 - Lease-aware execution claims + orphan reconciliation

## 배경 / 문제

Step 12~16을 거치면서 execution plane은 충분히 강해졌지만, 아직 실행 소유권과
회수 semantics에는 다음 틈이 남아 있습니다.

- 동일 run/task를 여러 worker가 동시에 잡을 수 있는 여지가 남아 있다
- CLI 종료나 프로세스 중단 이후 in-flight execution이 orphan 상태로 남을 수 있다
- approval-sensitive mutation이 multi-worker 환경에서 lease 없이 경쟁할 수 있다
- snapshot freshness는 보이지만, execution ownership까지 합쳐진 claim model은 아직 없다

즉 지금 필요한 것은 더 똑똑한 worker가 아니라, **누가 지금 이 실행을 합법적으로
소유하고 있는지**를 시스템 레벨에서 typed하게 관리하는 것입니다.

## 이번 단계의 목적

- execution dispatch에 lease-aware claim 모델을 도입합니다
- stale snapshot과 live execution ownership을 함께 고려하는 dispatch guard를 만듭니다
- orphaned execution / cancelled execution을 typed reclaim path로 회수합니다
- approval-sensitive 경로를 lease-aware concurrency gate로 보강합니다
- replay / audit / founder surface에서 lease lifecycle이 보이게 만듭니다

## 구현 범위

- run/task execution claim 모델 추가
- lease owner / acquired_at / expires_at / heartbeat or equivalent metadata
- dispatch 전 lease claim 획득
- 유효 lease 없는 mutation 거부 또는 typed refusal
- cancelled / crashed / expired execution reclaim path
- provider/container/worker execution 상태를 receipt/audit로 reconcile
- approval-sensitive mutation 경계에 lease-aware guard 추가
- 관련 CLI/status/replay visibility 추가
- ADR / implementation note / risk register 반영
- reclaim은 optimistic grace가 아니라 **pessimistic reclaim** 기준으로 동작
  - TTL/lease slack은 lease 설계 안에 포함
  - 만료 판정 이후에는 기존 worker 결과를 인정하지 않음
  - reclaim 전 가능한 경우 runtime-specific hard reclaim/container kill을 먼저 시도

## 이번 단계에서 하지 않는 것

- full distributed scheduler
- arbitrary multi-region coordination
- generic queue broker 도입
- runtime scoring rewrite
- full background daemon orchestration platform

## Acceptance Criteria

- 동일 run에 대해 live execution claim이 있으면 competing dispatch는 typed refusal로 막힌다
- expired lease나 crashed execution은 reclaim path를 통해 founder-visible 상태로 전환된다
- cancellation/orphan은 silent loss가 아니라 typed receipt/audit로 남는다
- approval-sensitive mutation은 lease-aware guard를 거친다
- replay와 status surface에서 execution claim lifecycle이 보인다
- 테스트로 stale claim, competing dispatch, reclaim, approval race 경계를 증명한다

## 리스크 연결

- 직접 타깃:
  - `RISK-0005` RunSnapshot staleness under concurrent writes
  - `RISK-0021` local/provider cancellation orphan semantics
  - `RISK-0022` multi-worker approval concurrency
- 이번 단계에서 추가로 드러난 리스크:
  - `RISK-0046` lease starvation / reclaim deadlock
  - `RISK-0047` atomic claim failure
  - `RISK-0048` reclaim side-effects without fencing
- 후속으로 남는 것:
  - `RISK-0039` manifest vs runtime reality gap
  - `RISK-0036` image bloat / pull latency
  - `RISK-0026` routing policy sprawl

## 연결 문서

- `docs/issues/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md`
- `docs/issues/STEP_15_PATCH_INTAKE_POLICY_AND_BOUNDED_AUTO_APPLY.md`
- `docs/issues/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md`
- `docs/risk-register/entries/2026-04-16-run-snapshot-staleness.md`
- `docs/risk-register/entries/2026-04-17-provider-cancellation-orphan.md`
- `docs/risk-register/entries/2026-04-17-multi-worker-approval-concurrency.md`
