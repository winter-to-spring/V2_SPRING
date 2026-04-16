# [운영] Shared risk register 운영 규칙 및 capability gate 정책

## 배경 / 문제

리스크를 사람 머릿속이나 대화 맥락에만 두면, 다른 세션이나 다른 작업자가
이어받을 수 없습니다.

V2_SPRING은 자율형 시스템을 목표로 하지만, 리스크 관리만큼은 "누가 기억하고
있느냐"에 의존하면 안 됩니다.

따라서 리스크는 repo 안의 shared artifact로 남아야 하고, capability gate와
직접 연결되어야 합니다.

## 이번 단계의 목적

1. shared risk register를 repo 공식 운영 레이어로 고정합니다.
2. 리스크 분류 기준을 `Now / Before Next Phase / Before Scale / Later Hardening`
   으로 통일합니다.
3. 언제 GitHub issue로 승격하는지 규칙을 정합니다.
4. capability gate와 리스크 기록을 연결합니다.

## 구현 범위

- `docs/risk-register/README.md` 작성
- 초기 risk entry 3건 등록
- docs index에 risk register 연결
- capability gate 중심의 리스크 처리 규칙 명문화

## Acceptance Criteria

- repo 안에서 shared risk register 위치가 명확하다
- 분류 기준이 문서에 명시되어 있다
- 즉시 이슈화 vs 레지스터 보관 기준이 있다
- capability gate와 리스크의 연결 방식이 문서로 남아 있다
