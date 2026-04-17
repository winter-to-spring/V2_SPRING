# [코어] Step 15 - Patch intake policy routing + bounded auto-apply lane

## 배경 / 문제

Step 12-c까지 오면서 worker patch는 모두 founder review gate를 통과해야 했습니다.

이건 초기 trust 확보에는 맞았지만, 모든 patch에 같은 review cost를 부과하면
execution plane throughput이 founder attention에 의해 병목됩니다.

특히 이미 낮은 위험도로 분류되고, 단일 파일만 만지며, dangerous keyword나
sensitive path warning도 없는 patch까지 항상 수동 review를 요구하는 것은
과도합니다.

## 이번 단계의 목적

- patch intake의 `risk_class` / `auto_apply_eligible`를 실제 정책으로 연결합니다
- founder review를 기본값으로 유지하되, 아주 좁은 low-risk lane만 strict
  auto-apply를 허용합니다
- auto-apply도 founder approve와 동일하게 strict patch apply + bounded validation을
  반드시 거칩니다
- auto-apply 성공/실패는 replay와 ledger에 명확히 남깁니다

## 구현 범위

- low-risk + bounded patch lane에 대한 auto-apply 정책 도입
- `PatchResolutionCode.AUTO_APPLIED` 추가
- patch intake resolution helper 정리
- auto-apply 성공 시
  - validation receipt artifact 기록
  - run completed 전이
  - system audit 기록
- auto-apply 실패 시
  - typed rejection code로 마감
  - run ready 전이
  - planner가 다시 접근할 수 있게 함
- 관련 테스트 추가
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- broad default auto-apply
- multi-file medium/high-risk patch auto-apply
- founder policy UI
- score-based trust system
- per-repo custom review policy DSL
- file centrality / protected module graph for semantic blast-radius control
- burst quota / anti-salami auto-apply throttling
- AST-level dangerous pattern analysis beyond simple keyword heuristics
- detailed planner repair guidance sourced from validation failure receipts

## Acceptance Criteria

- low-risk single-file patch는 founder review 없이 strict auto-apply될 수 있다
- auto-apply는 founder approve와 동일하게 strict apply + validation을 거친다
- auto-apply 성공은 `AUTO_APPLIED` resolution으로 남는다
- auto-apply 실패는 typed rejection으로 남고 run은 다시 `ready`가 된다
- high-risk / warning-bearing patch는 여전히 founder review gate를 탄다
- replay / status surface에서 auto-apply 결과가 보인다

## 리스크 연결

- 직접 타깃:
  - `RISK-0025` founder review bottleneck without risk-based patch intake routing
- 의도적 비대상:
  - broad trust-score system
  - fully dynamic patch policy registry
  - `RISK-0040` semantic chain reaction on central files
  - `RISK-0041` planner salami attack against bounded auto-apply
  - `RISK-0042` obfuscated dangerous pattern bypass

## 연결 문서

- `docs/issues/STEP_12C_PATCH_INTAKE_REVIEW_GATE.md`
- `docs/risk-register/entries/2026-04-17-patch-review-fatigue-and-routing.md`
- `docs/issues/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md`
