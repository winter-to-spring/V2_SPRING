# [코어] Step 12-c - Patch intake / founder review gate

## 배경 / 문제

isolated worker가 patch/artifact/receipt를 만들어도,
그 결과를 메인 흐름에 **어떻게 받아들이고 거절할지**가 없으면 execution plane은
속도만 빠른 외부 장치에 머뭅니다.

Step 12-c는 worker output을 founder/operator가 review하고,
control plane이 replayable하게 intake/apply/reject 하는 gate를 만드는 단계입니다.

## 이번 단계의 목적

1. worker output intake contract를 정의한다.
2. founder/operator가 compact하게 patch/result를 review할 수 있게 한다.
3. approve/reject 후속 상태 전이를 typed하게 만든다.
4. worker output intake가 replay trail과 이어지게 한다.
5. future multi-runtime execution plane의 안전한 병합 경로를 연다.

## 구현 범위

- patch intake typed model
- unified patch contract as the primary intake format
- base file hash / conflict-aware apply validation
- strict all-or-nothing patch apply policy
- bounded validation step after apply
- compact review warnings
  - danger keyword/path scan
  - patch size / touched-file count summary
- compact review surface
- raw diff / raw receipt escape hatch
- founder approve/reject gate
- review policy metadata
  - risk class
  - auto-apply eligibility hook
- apply/reject ledger trail
- artifact / receipt linkage 강화
- CLI proof
  - 예: `v2-spring patch review <run-id>`
  - `v2-spring patch approve <id>`
  - `v2-spring patch reject <id>`
- 관련 docs / tests 반영

## 이번 단계의 핵심 결정

1. **Worker output은 founder review 가능한 형태로 먼저 들어온다**
- 자동 merge/apply를 기본값으로 두지 않습니다

2. **Compact summary + raw escape hatch**
- founder/operator는 compact summary를 먼저 보고
- 필요할 때만 raw diff/receipt를 열 수 있어야 합니다

3. **Apply/reject는 replay 가능한 상태 전이**
- patch intake 이후의 founder 판단도 원장에 명시적으로 남깁니다

4. **Worker patch는 unified patch를 기본 형식으로 사용**
- full file replacement를 기본값으로 쓰지 않습니다
- patch review, diff visibility, selective rejection을 위해 표준 unified patch를 우선 사용합니다
- 필요한 경우 원본/결과 파일은 보조 artifact로 첨부할 수 있습니다

5. **Review fatigue는 policy hook으로 먼저 다룸**
- 첫 proof에서는 founder review를 기본 경로로 유지하되
  risk class와 auto-apply eligibility metadata를 intake model에 포함합니다
- 이후 low-risk / read-only / non-destructive classes부터 bounded auto-apply를 열 수 있게 준비합니다

6. **Patch apply는 strict all-or-nothing**
- fuzzy partial apply를 허용하지 않습니다
- unified patch context가 조금이라도 맞지 않으면 apply를 거부합니다
- patch rejection은 명확한 실패로 기록하고, 최신 snapshot/base context를 기준으로 다시 패치를 짜게 해야 합니다

7. **Syntactic apply만으로 성공 처리하지 않음**
- patch가 기계적으로 적용되더라도 바로 validation step을 태웁니다
- 최소 `compileall` 또는 동등한 cheap validation을 기본으로 둡니다
- validation이 실패하면 apply 성공이 아니라 rejected validation failure로 기록합니다

8. **Founder review surface는 인라인 diff가 기본**
- 첫 proof에서는 CLI inline diff/summary를 기본으로 둡니다
- 외부 에디터에서 founder가 패치를 직접 고치는 흐름은 기본 경로로 열지 않습니다
- 필요할 때만 raw diff/receipt artifact를 여는 escape hatch를 둡니다

9. **적용된 diff 원문은 계속 artifact로 보존**
- replay가 미래 파일 상태에 의존하지 않도록
  승인/적용된 unified diff 원문 자체를 artifact로 영구 보존합니다

## 이번 단계에서 하지 않는 것

- fully autonomous merge to mainline
- distributed review queue
- org-wide code owner policy engine
- broad default auto-apply for code patches
- founder-side patch editing inside an external editor

## Acceptance Criteria

- worker output intake model이 typed contract로 존재한다
- primary intake format이 unified patch로 고정된다
- patch apply 전에 base hash conflict validation이 가능하다
- patch apply는 strict all-or-nothing으로만 수행된다
- apply 직후 validation 결과가 founder/operator surface와 ledger에 남는다
- founder/operator가 compact review surface에서 결과를 읽을 수 있다
- review surface가 danger scan / patch size / touched-file count를 보여준다
- raw diff/receipt artifact를 열 수 있는 escape hatch가 있다
- approve/reject가 ledger에 replayable하게 남는다
- risk class / auto-apply eligibility metadata가 review surface에 나타난다
- apply/reject 이후 상태 전이가 founder/operator에게 명확히 보인다
- applied unified diff 원문이 artifact로 계속 남는다

## 연결 문서

- `docs/issues/STEP_12_EXECUTION_PLANE_EPIC.md`
- `docs/issues/STEP_12B_ISOLATED_WORKER_PROOF.md`
- `docs/implementation-notes/STEP_11_FOUNDER_OPERATOR_PROGRESS_SURFACE.md`
- `docs/risk-register/entries/2026-04-17-patch-review-fatigue-and-routing.md`
- `docs/risk-register/entries/2026-04-17-patch-semantic-conflict-after-apply.md`
- `docs/risk-register/entries/2026-04-17-patch-review-danger-blindness.md`
