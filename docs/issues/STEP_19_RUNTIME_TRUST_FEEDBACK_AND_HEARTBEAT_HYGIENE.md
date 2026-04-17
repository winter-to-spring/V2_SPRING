# [코어] Step 19 - Runtime trust feedback + heartbeat hygiene

## 배경 / 문제

Step 18까지 오면서 execution ownership, reclaim, fencing은 현재 스코프에서
상당히 단단해졌습니다.

하지만 실행 평면의 신뢰성과 운영 효율에는 아직 두 가지 직접적인 빈틈이
남아 있습니다.

- static capability manifest가 실제 runtime health와 어긋날 수 있다
- lease renewal은 thresholded 되었지만, worker 수가 늘면 여전히 renewal
  traffic 자체가 scale bottleneck이 될 수 있다

즉 Step 19의 목적은 새로운 runtime을 여는 것이 아니라,
**이미 열린 runtime을 더 믿을 수 있고 더 싸게 운영할 수 있게 만드는 것**입니다.

## 이번 단계의 목적

- manifest와 실제 runtime health 사이의 신뢰 피드백 루프를 추가합니다
- observed mismatch가 반복될 때 dynamic admission check로 승격되는 규칙을 만듭니다
- lease renewal write churn을 더 줄이는 heartbeat hygiene를 도입합니다
- founder/operator surface에서 runtime trust degradation과 renewal pressure를 읽을 수 있게 합니다
- 리스크 장부에서 실제로 줄일 수 있는 `RISK-0039`, `RISK-0049`를 직접 깎습니다

## 구현 범위

- repo-managed worker metadata registry를 기준 truth로 유지
- runtime capability failure observation 누적
- runtime trust state / strike / downgrade metadata
- static-first preflight에서 selective dynamic preflight로 승격되는 규칙
- repeated mismatch에 대한 typed refusal / repairable feedback
- claim renewal write coalescing 또는 bounded renewal cadence 강화
- renewal churn에 대한 founder/operator-visible audit summary
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- networked worker runtime 개방
- external API side-effect fencing
- image-pool / pull-cache 최적화
- generalized dynamic scoring registry

## Acceptance Criteria

- static manifest가 반복적으로 빗나갈 때 시스템이 같은 lane을 맹신하지 않는다
- 중요한 capability mismatch는 vague crash가 아니라 typed runtime trust signal로 보인다
- lease renewal traffic이 현재 thresholded renewal보다 더 억제된다
- founder/operator surface에서 runtime trust degradation과 renewal pressure를 읽을 수 있다
- `RISK-0039`, `RISK-0049`가 Step 19 범위에서 직접 줄거나 닫힌다
- `RISK-0051`은 여전히 networked/external-effect runtime 전용 리스크로 분리 유지된다

## 리스크 연결

- 직접 타깃:
  - `RISK-0039` manifest vs runtime reality gap
  - `RISK-0049` heartbeat storm under lease renewal
- 이번 단계에서 의도적으로 남기는 것:
  - `RISK-0051` external side-effect ghost
    - 아직 `--network none` 경계를 유지하고 있으므로, networked/external-effect runtime을 열기 전까지는 후속 리스크로 유지
- 후속으로 남는 것:
  - `RISK-0036` image bloat / pull latency
  - `RISK-0026` routing policy sprawl
  - `RISK-0006` read-model growth
  - `RISK-0045` shadow centrality beyond protected paths

## 연결 문서

- `docs/issues/STEP_18_LEASE_RENEWAL_AND_FENCED_RECLAIM_HARDENING.md`
- `docs/adr/0016-lease-renewal-fencing-and-stale-result-rejection.md`
- `docs/risk-register/entries/2026-04-17-manifest-reality-gap.md`
- `docs/risk-register/entries/2026-04-17-heartbeat-storm-under-lease-renewal.md`
- `docs/risk-register/entries/2026-04-17-external-side-effect-ghost-after-reclaim.md`
