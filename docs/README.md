# 문서 맵

- `adr/` - 아키텍처 결정과 약속
- `architecture/` - 시스템 구조와 단계별 빌드 계획
- `charter/` - 제품 의도, 경계, 비목표
- `risk-register/` - 공용 운영 리스크, capability gate, 에스컬레이션 시점
- `specs/` - tracer bullet 같은 구현 지향 스펙
- `verification/` - founder/operator 검증 방식
- `runbooks/` - 운영 절차

보관용 V1 문서는 [`archive/v1/`](../archive/v1/) 아래에 있습니다.

## 이슈 제목 규칙

새 GitHub 이슈는 먼저 스트림 태그로 시작합니다.

- `[engine]`
- `[product]`

그다음 아래 실행 prefix 중 하나를 붙입니다.

- `[코어]`
- `[UI]`
- `[운영]`
- `[인프라]`
- `[문서]`
- `[검증]`

권장 형식:

- `[engine] [코어] Step 23 - ...`
- `[product] [UI] Step P1 - ...`

운영 규칙과 예시는 [Issue Stream Labeling](/Users/changhyeon/Desktop/AI%20AGENT/docs/charter/ISSUE_STREAM_LABELING.md)
문서를 참고하세요.
