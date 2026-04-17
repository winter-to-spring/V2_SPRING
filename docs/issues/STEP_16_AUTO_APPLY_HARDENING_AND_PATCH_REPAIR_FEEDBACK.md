# [코어] Step 16 - Auto-apply trust hardening + patch repair feedback

## 배경 / 문제

Step 15에서 bounded auto-apply lane을 열면서 founder review bottleneck은 줄었지만,
새로운 trust hardening 요구가 명확해졌습니다.

현재 auto-apply lane은 의도적으로 좁지만, 다음 세 가지 틈이 남아 있습니다.

- 낮은 변경량이어도 전역적 의미를 가진 파일이 자동 적용될 수 있다
- planner가 큰 변경을 여러 개의 작은 patch로 쪼개 auto-apply lane을 악용할 수 있다
- 단순 dangerous keyword scan은 우회될 수 있다
- 상세한 repair feedback이 오히려 무의미한 자동 수리 루프를 길게 끌 수 있다

또한 auto-apply 실패 시 planner가 재시도하기는 가능하지만, 실패 이유가 충분히
구조화되어 전달되진 않습니다.

## 이번 단계의 목적

- auto-apply lane에 semantic blast-radius guard를 추가합니다
- 연속 자동 적용에 대한 burst quota / anti-salami 정책을 추가합니다
- dangerous pattern scan을 더 강한 정적 분석으로 보강합니다
- auto-apply 실패를 planner-facing detailed repair feedback으로 연결합니다
- 반복 repair 실패에 대한 bounded quota와 founder escalation 경로를 추가합니다
- structural scan 결과를 hard block과 soft warning으로 분리합니다

## 구현 범위

- protected path / central file policy 도입
- 동일 파일 / 동일 모듈에 대한 bounded auto-apply burst guard
- keyword heuristic을 보강하는 lightweight structural scan 도입
- patch validation 실패 receipt를 planner-facing failure report로 연결
- 동일 목표/동일 파일 repair retry quota 도입
- structural scan을 strict block 과 soft warning으로 분리
- 관련 테스트 추가
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- full semantic dependency graph
- dynamic centrality score / reference graph
- per-repo custom auto-apply policy DSL
- full trust scoring engine
- unrestricted broad auto-apply

## Acceptance Criteria

- central/protected file은 단일 파일이어도 auto-apply에서 제외된다
- 짧은 기간 내 반복 auto-apply 시도는 typed refusal 또는 founder review fallback으로 전환된다
- obvious obfuscated dangerous patterns는 simple keyword scan보다 더 강하게 차단된다
- auto-apply validation failure는 planner가 수리 가능한 형태의 상세 실패 피드백으로 남는다
- repair retry quota를 넘기면 founder escalation 또는 equivalent bounded stop으로 전환된다
- structural scan warning은 hard block과 soft warning으로 구분되어 founder surface에 드러난다
- replay / audit / founder surface에서 auto-apply hardening 결과가 보인다

## 리스크 연결

- 직접 타깃:
  - `RISK-0040` semantic chain reaction from low-risk auto-apply on central files
  - `RISK-0041` planner salami attack against bounded auto-apply
  - `RISK-0042` obfuscated dangerous pattern bypass
  - `RISK-0043` repair loop deadlock after detailed patch feedback
  - `RISK-0044` false-positive friction from lightweight structural scan
- 1차 완화:
  - `RISK-0045` shadow centrality beyond the initial protected file list

## 연결 문서

- `docs/issues/STEP_15_PATCH_INTAKE_POLICY_AND_BOUNDED_AUTO_APPLY.md`
- `docs/risk-register/entries/2026-04-17-semantic-chain-reaction-on-auto-apply.md`
- `docs/risk-register/entries/2026-04-17-auto-apply-salami-attack.md`
- `docs/risk-register/entries/2026-04-17-obfuscated-dangerous-pattern-bypass.md`
- `docs/risk-register/entries/2026-04-17-repair-loop-deadlock-after-detailed-feedback.md`
- `docs/risk-register/entries/2026-04-17-structural-scan-false-positive-friction.md`
- `docs/risk-register/entries/2026-04-17-shadow-centrality-beyond-protected-paths.md`
