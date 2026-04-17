# Risk ID: RISK-0036
Title: 컨테이너 worker 이미지 비대화가 pull latency를 키우고 execution plane 반응성을 떨어뜨릴 수 있음
Class: Before Scale
Status: Open
Owner: Execution plane / Worker image strategy
Observed In: Step 14 provenance and capability-preflight planning

## 설명

Step 14는 첫 번째 container runtime을 static image 위에 고정하는 올바른
선택을 했지만, 그만큼 미래 압력도 생깁니다. 도구와 capability manifest가
추가될수록 이미지가 매우 큰 "super image"로 커질 수 있습니다.

그 시점이 되면 시스템은 논리적으로는 맞더라도 운영적으로 느려질 수 있습니다.

- cold start가 느려진다
- 새 노드가 이미지 pull에 긴 시간을 쓴다
- 실제 작업이 시작되기 전부터 dispatch latency가 증가한다

## 영향

- execution plane이 속도 이점을 잃는다
- 새 환경의 복구와 scale-out이 느려진다
- "runtime is healthy"와 "runtime is usable"가 어긋나 디버깅이 더 시끄러워진다

## 왜 중요한가

V2_SPRING은 명시적이고 결정론적인 runtime policy를 선호해야 하지만, 그게
아무 통제 없이 수 GB worker image로 커지는 결과로 이어지면 안 됩니다.

이건 첫 proof lane의 Step 14 blocker는 아니지만, 더 넓은 worker capability
확장이나 multi-node rollout 전에는 중요해집니다.

## 권장 완화책

- proof/runtime image를 의도적으로 좁게 유지한다
- 이미지 capability 증가를 worker contract 변경과 분리한다
- scale 전에 pre-pulled image pool, layered image, capability별 image 분리를 검토한다
- image 크기와 cold-start 기대치를 runtime ops 문서에 드러낸다

## Capability Gate
- Capability: broad containerized worker capability expansion and multi-node use
- Gate mode: Before Scale
- Blocked until: image growth has an explicit strategy so pull latency does not
  undermine execution-plane responsiveness

## Issue Link
- GitHub Issue: #37

## Doc Links
- ADR:
- Design note: ../../docs/issues/STEP_14_CONTAINER_RUNTIME_PROVENANCE_AND_GUARDRAILS.md

## 종료 기준

- 이미지 증가가 측정되고 bounded하게 관리된다
- capability 확장이 하나의 무한정 커지는 "super image"에 의존하지 않는다
- cold-start / pull 동작이 이해 가능하고 운영적으로 수용 가능하다

## Last Updated
- 2026-04-17
