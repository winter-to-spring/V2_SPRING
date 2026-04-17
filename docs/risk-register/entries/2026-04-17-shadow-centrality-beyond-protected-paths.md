# Risk ID: RISK-0045
Title: 정적 protected-path 목록이 초기 trust boundary 밖의 의미상 핵심 파일을 놓칠 수 있음
Class: Later Hardening
Status: Mitigating
Owner: Patch intake policy / file centrality model
Observed In: Step 16 protected-file planning

## 설명

명시적인 protected-file 목록은 좋은 첫 하드닝 단계지만, 초기 수동 목록에는
없어도 의미상 중요도가 높은 파일은 놓칠 수 있습니다.

## 영향

- 의미상 중앙에 있는 파일이 누락 때문에 auto-apply 대상에 남을 수 있음
- founder가 초기 protected-file 경계를 과신할 수 있음
- blast-radius 제어가 부분적으로 수동이고 불완전한 상태로 남음

## 왜 중요한가

정적 protected path는 강한 첫 방어선이지만, 완전한 centrality model은 아닙니다.

팀은 이 간극을 명시적으로 추적해야 하며, 첫 구현이 최종 해법으로 오해되지
않게 해야 합니다.

## 권장 완화책

- 보수적인 protected-file 목록으로 시작한다
- 이후 reference count, module fan-out, test blast-radius signal을 검토한다
- 숨은 부채로 두지 말고 명시적인 hardening backlog로 유지한다

## 현재 완화 상태

Step 16은 첫 번째 protected-file / central-file 정책을 도입했기 때문에, 이
리스크는 더 이상 완전히 무방비 상태는 아닙니다.

현재 경계는 의도적으로 정적이고 보수적이며, 지금은 유용하지만 더 넓은
autonomous trust 관점에서는 아직 불완전합니다.

## Capability Gate
- Capability: broader safe auto-apply beyond trivial or manually protected files
- Gate mode: Later Hardening
- Blocked until: dynamic or richer centrality signals supplement static path lists

## Issue Link
- GitHub Issue: #39

## Doc Links
- ADR: ../../adr/0014-auto-apply-trust-hardening-and-repair-feedback.md
- Design note: ../../implementation-notes/STEP_16_AUTO_APPLY_HARDENING_AND_PATCH_REPAIR_FEEDBACK.md

## 종료 기준

- centrality model이 초기 protected-file allow/deny 목록을 넘어 확장된다

## Last Updated
- 2026-04-17
