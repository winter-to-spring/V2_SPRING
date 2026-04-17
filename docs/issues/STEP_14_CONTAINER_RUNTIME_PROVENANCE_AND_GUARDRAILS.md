# [코어] Step 14 - Container runtime provenance + bounded log hygiene + capability preflight

## 배경 / 문제

Step 13까지 오면서 V2_SPRING은 containerized worker runtime proof를 확보했습니다.

- static image 기반의 containerized worker lane
- `docker cp` copy-in / copy-out air-gap
- least-privilege container launch policy
- ownership normalization
- timeout reclaim + orphan GC

이로써 `RISK-0027`, `RISK-0030`, `RISK-0031`, `RISK-0032`는 닫혔습니다.

하지만 Step 13이 닫은 것은 **containerized runtime contract의 1차 증명**이고,
실전 worker capability를 더 넓히기 전에 다음 세 가지 잔여 리스크를 닫아야 합니다.

- `RISK-0033` image integrity / replay drift without digest-pinned provenance
- `RISK-0034` container log explosion / host disk exhaustion during copy-out
- `RISK-0035` runtime environment gap once containerized capabilities expand
- `RISK-0037` local metadata snapshot drift across environments
- `RISK-0038` tail-only log capture may hide the real root cause
- `RISK-0039` manifest metadata can drift away from actual runtime health

즉 Step 14의 목적은 새로운 worker lane을 더 여는 것이 아니라,
**Step 13에서 확보한 containerized runtime을 더 재현 가능하고, 더 bounded하고, 더 capability-aware하게 만드는 것**입니다.

## 이번 단계의 목적

- containerized worker image provenance를 더 엄격하게 고정합니다
- runaway container log가 host disk를 잠식하지 못하게 bounded policy를 도입합니다
- capability expansion 전에 runtime/image compatibility를 preflight로 검증합니다
- dispatch가 외부 registry availability에 직접 묶이지 않도록 local metadata snapshot을 기준으로 판단합니다
- local metadata snapshot 자체가 환경마다 drift하지 않도록 metadata registry consistency를 강제합니다
- tail-only가 아니라 sandwich-style diagnostics로 중요한 초기/후기 로그 단서를 함께 남깁니다
- typed refusal / receipt / replay contract는 유지합니다

이번 단계에서 metadata snapshot은 별도 DB가 아니라 **repo-managed JSON/YAML artifact**
로 관리합니다.

예상 위치:

- `infra/worker_manifest.yaml`
- 또는 동등한 repo-tracked metadata registry file

## 구현 범위

- static image digest provenance 정책 도입
- receipt에 image digest 또는 동등한 immutable identity 추가
- local metadata snapshot / capability manifest policy 추가
- dispatch는 registry live query 없이 local metadata snapshot을 사용하도록 고정
- metadata registry checksum / version strategy 추가
- repo-managed metadata registry file path / schema version policy 정의
- container log file bounded policy 추가
- head+tail sandwich log capture + oversized log guard 또는 overflow receipt 추가
- runtime capability manifest 또는 preflight check 도입
- static-first preflight + selective dynamic admission-check 경계 정의
- observed runtime mismatch 시 manifest trust를 낮추고 dynamic admission-check로 escalation하는 정책 정의
- requirements와 image capability 간 compatibility refusal 경로 추가
- 관련 CLI / replay / progress surface 보강
- 관련 테스트 추가
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- multi-worker scheduling
- autoscaling
- dynamic image build pipeline
- review fatigue / auto-apply routing
- distributed concurrency hardening

## 구체 작업 항목

- container image provenance model 정의
- digest-pinned runtime metadata 설계
- oversized log detection / overflow receipt 설계
- bounded log copy-out 정책 구현
- worker capability manifest 또는 equivalent runtime assumptions 모델 정의
- capability preflight / compatibility refusal 구현
- replay/progress surface에 새 runtime guardrail 노출
- 테스트 추가
- ADR / implementation note 작성

## Acceptance Criteria

- containerized runtime provenance가 mutable tag만으로 표현되지 않는다
- replay/receipt에서 runtime image identity를 확인할 수 있다
- dispatch/preflight는 registry live availability가 아니라 local metadata snapshot을 기준으로 동작한다
- metadata registry는 환경 간 일관된 checksum/version 경계를 가진다
- metadata registry는 repo-managed JSON/YAML artifact로 version control 안에서 관리된다
- runaway container log가 무한 copy-out으로 host disk를 잠식하지 못한다
- oversized log는 typed overflow/guard receipt로 회수되거나 head+tail sandwich strategy로 bounded 진단 정보를 남긴다
- expanded worker capability dispatch 전에 runtime compatibility를 preflight로 검증한다
- compatibility mismatch는 vague runtime crash가 아니라 typed refusal/failure로 보인다
- 테스트가 통과한다

## 리스크 / 메모

- 이번 단계의 핵심 closure 대상:
  - `RISK-0033`
  - `RISK-0034`
  - `RISK-0035`
  - `RISK-0037`
  - `RISK-0038`
- 이번 단계에서 흡수하는 설계 포인트:
  - local metadata snapshot으로 registry dependency 차단
  - metadata registry consistency로 routing determinism 유지
  - sandwich log hygiene로 진단 정보 보존
  - static-first, selective-dynamic preflight split
- 우선순위 판단:
  - `RISK-0037` 높음
  - `RISK-0038` 중간
  - `RISK-0039` 중간~낮음
- 아직 범위 밖:
  - `RISK-0021`
  - `RISK-0022`
  - `RISK-0025`
  - `RISK-0026`
  - `RISK-0036`
  - `RISK-0039` (1차 완화는 이번 단계에서, 완전 closure는 후속 capability expansion과 함께)

## 연결 문서

- `docs/issues/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md`
- `docs/implementation-notes/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md`
- `docs/risk-register/entries/2026-04-17-container-image-integrity-and-replay-drift.md`
- `docs/risk-register/entries/2026-04-17-container-log-explosion-and-copy-out-disk-risk.md`
- `docs/risk-register/entries/2026-04-17-container-runtime-environment-gap.md`
- `docs/risk-register/entries/2026-04-17-metadata-snapshot-fragmentation.md`
- `docs/risk-register/entries/2026-04-17-log-diagnostic-sandwich-blindspot.md`
- `docs/risk-register/entries/2026-04-17-manifest-reality-gap.md`

## 기대 결과

Step 14가 끝나면 containerized worker runtime은

- "격리된 proof lane"
에서
- "재현 가능성과 bounded 운영성까지 갖춘 확장 가능한 runtime lane"

으로 한 단계 더 올라가 있어야 합니다.
