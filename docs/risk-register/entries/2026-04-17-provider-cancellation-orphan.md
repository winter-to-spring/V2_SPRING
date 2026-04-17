# Risk ID: RISK-0021
Title: 로컬 CLI 취소 이후 터미널이 종료되면 진행 중인 provider 호출이 orphan 상태로 남을 수 있음
Class: Before Scale
Status: Mitigating
Owner: Core / Planner transport
Observed In: Step 10-c production transport hardening

## 설명

Step 10-c는 Python이 `KeyboardInterrupt`를 받을 때 로컬 취소를 typed
transport error로 정규화합니다.

이 덕분에 replay 가능성과 오류 분류는 좋아졌지만, upstream provider가
실제로 과금과 요청 처리를 멈췄는지까지 보장하지는 못합니다.

founder가 provider 호출이 아직 진행 중일 때 로컬에서 `planner invoke`를
중단하면, control plane은 기다리기를 멈추지만 원격 provider는 한동안 계속
처리할 수 있습니다.

## 영향

- 로컬 CLI는 "cancelled"라고 보이지만 원격 과금은 계속될 수 있음
- 반복 취소가 혼란스러운 audit trail과 숨은 비용 드리프트를 만들 수 있음
- 향후 background execution은 현재 foreground CLI보다 더 강한 cancellation semantics가 필요함

## 왜 중요한가

현재 transport seam은 많은 network/provider failure에 더 잘 버티지만, 진짜
orphan 방지는 단순 CLI signal 처리보다 더 강한 request lifecycle 제어가
필요합니다.

planner invocation을 background worker나 장시간 유지되는 founder surface로
확장하려면 cancellation semantics를 더 명시적으로 만들어야 합니다.

## 권장 완화책

- 호출별 timeout을 bounded하게 유지해 orphan 노출 범위를 줄인다
- 로컬 취소를 구조화된 audit evidence로 기록한다
- scale 전에 provider 측 idempotency 또는 cancellation handle을 검토한다
- planner transport를 foreground CLI 밖으로 옮기기 전에 worker-safe cancellation policy를 추가한다

현재 완화 상태:

- 로컬 취소는 typed `PlannerTransportCancelledError`로 정규화됨
- cancellation audit observation에는 다음이 포함됨
  - `timeout_seconds`
  - `orphan_risk_possible`
  - `cancellation_scope=local_cli_only`
  - founder를 위한 bounded reinvocation hint
- Step 20은 두 번째 reconciliation audit를 추가해 replay가 아래를 구분하게 함
  - cancellation intent
  - local reconciliation / bounded orphan-risk finalization
- transport test와 CLI test가 cancellation path를 명시적으로 검증함

## Capability Gate
- Capability: background planner workers / long-running planner invokes
- Gate mode: Before Scale
- Blocked until: 로컬 abort가 조용한 provider 비용으로 이어지지 않을 만큼
  cancellation semantics가 명시적이어야 함

## Issue Link
- GitHub Issue: #23, #46

## Doc Links
- ADR: ../../adr/0009-production-planner-transport-seam.md
- ADR: ../../adr/0018-snapshot-freshness-and-cancellation-reconciliation.md
- Design note: ../../implementation-notes/STEP_10C_PRODUCTION_TRANSPORT_HARDENING.md
- Design note: ../../implementation-notes/STEP_20_SNAPSHOT_FRESHNESS_AND_CANCELLATION_RECONCILIATION.md

## 종료 기준

- planner invocation이 로컬 CLI interrupt를 넘는 bounded cancellation semantics를 지원한다
- 장시간 또는 background planner execution이 숨은 provider 비용 없이 interrupted request를 reconcile할 수 있다

## Last Updated
- 2026-04-17
- 2026-04-17 (mitigating)
- 2026-04-17 (Step 20 reconciliation audit)
