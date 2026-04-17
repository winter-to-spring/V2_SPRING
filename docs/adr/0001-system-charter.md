# ADR-0001: 시스템 차터

## 상태

Accepted

## 배경

V1은 안정적인 제품 차터 없이 orchestration, runtime coupling, UI 실험이
뒤섞여 있었습니다. 그 결과 검증은 어려워지고, 임시 패치가 취약성을 더 키우는
구조가 되었습니다.

## 결정

V2_SPRING은 founder가 통제하는 자율 소프트웨어 스튜디오를 클린룸 방식으로
재구축합니다. 이는 V1 Paperclip 제품 표면의 연장이 아닙니다.

## 결과

- 우리는 durable state와 governable autonomy를 먼저 최적화합니다.
- UI polish는 첫 번째 마일스톤이 아닙니다.
- 기존 V1 산출물은 핵심 빌딩 블록이 아니라 보관용 참고 자료로 취급합니다.
