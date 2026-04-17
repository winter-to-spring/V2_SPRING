# [코어] Step 20 - Snapshot freshness + cancellation reconciliation hardening

## 배경 / 문제

Step 19까지 오면서 runtime trust, lease renewal, reclaim, fencing은 현재
스코프에서 꽤 단단해졌습니다.

하지만 코어 운영 무결성 관점에서 아직 두 가지 직접적인 빈틈이 남아
있습니다.

- stale snapshot 기반 제안/dispatch/mutation을 더 명시적으로 거절해야 한다
- local cancel / orphan 상황을 silent loss가 아니라 typed reconciliation으로
  끝내야 한다

즉 Step 20의 목적은 새로운 runtime을 여는 것이 아니라,
**코어 무결성의 마지막 모서리를 다듬는 것**입니다.

## 이번 단계의 목적

- snapshot freshness token 또는 generation metadata를 도입합니다
- stale snapshot 기반 변경/dispatch 경로를 typed refusal로 고정합니다
- cancellation intent와 final reconciliation을 분리합니다
- orphan/cancel 결과를 founder/operator surface에서 읽을 수 있게 합니다
- 리스크 장부에서 실제로 줄일 수 있는 `RISK-0005`, `RISK-0021`를 직접
  깎습니다

## 구현 범위

- snapshot freshness token / generation
- stale mutation / stale dispatch / stale patch-intake guard 강화
- cancellation intent event + final reconciliation outcome
- orphan/cancel typed receipt / audit trail
- founder/operator surface 노출
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- distributed multi-node scheduler
- generalized external side-effect compensation
- 성능 최적화만을 위한 read-model 재설계

## Acceptance Criteria

- stale snapshot 기반 변경 시도가 typed refusal로 귀결된다
- cancellation은 intent -> reconciliation -> final status 흐름으로 기록된다
- orphan/cancel 결과가 replay/progress surface에서 읽힌다
- `RISK-0005`, `RISK-0021`가 Step 20 범위에서 직접 줄거나 닫힌다

## 리스크 연결

- 직접 타깃:
  - `RISK-0005` RunSnapshot staleness under concurrent writes
  - `RISK-0021` Local CLI cancellation may leave an in-flight provider call orphaned after the terminal exits
- 후속으로 남는 것:
  - `RISK-0036` image bloat / pull latency
  - `RISK-0045` shadow centrality beyond protected paths
  - `RISK-0051` external side-effect ghost
  - `RISK-0026` routing policy sprawl
  - `RISK-0006` read-model growth
