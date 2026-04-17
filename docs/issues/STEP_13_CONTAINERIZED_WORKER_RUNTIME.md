# [코어] Step 13 - Containerized worker runtime + reclaim semantics

## 배경 / 문제

Step 12까지 오면서 V2_SPRING은 실행 평면의 핵심 계약을 증명했습니다.

- planner/control plane이 execution requirements를 결정한다
- isolated worker가 메인 상태를 직접 수정하지 않는다
- worker 결과는 patch / artifact / receipt로만 회수된다
- founder review gate가 strict patch intake를 통해 최종 적용 여부를 제어한다

하지만 현재 Step 12-b의 worker proof는 강화된 soft isolation에 머뭅니다.

- subprocess + task-local copied workspace
- env allowlist
- timeout reclaim
- temp-file log capture

이것만으로는 unrestricted bypass worker를 더 넓게 열기에 충분하지 않습니다.

현재 남아 있는 핵심 리스크는:

- `RISK-0027` soft-isolated worker proof lacks OS/container-level isolation
- `RISK-0021` local cancellation may leave an in-flight execution orphaned

즉 다음 단계는 “worker를 더 안전하게, 더 길게, 더 현실적인 실행 환경에서 돌려도 control plane이 안 망가진다”를 증명하는 것입니다.

## 이번 단계의 목적

- isolated worker runtime을 OS/container-level isolation 쪽으로 올립니다
- worker reclaim / timeout / cancel semantics를 receipt 기반으로 더 명확히 합니다
- Step 12의 patch / artifact / receipt 계약을 유지한 채 runtime만 강화합니다
- unrestricted bypass worker를 열기 전 필요한 최소 실행 안전장치를 갖춥니다

## 구현 범위

- containerized worker runtime adapter 도입
- static worker image 전략 고정
- task-local workspace mount/copy 정책 명시
- `.env` / host secret surface 차단
- least-privilege container policy (`docker.sock` 비마운트, `--privileged` 금지, no-new-privileges)
- ownership normalization for copied-out artifacts / logs / patched workspace state
- orphan container GC + reclaim labels
- hard timeout + process/container reclaim
- cancel / timeout / crash를 typed receipt로 회수
- bounded stdout/stderr or log artifact strategy 유지
- CLI proof surface 추가 또는 기존 `task dispatch` 확장
- replay / progress / audit에 container worker lifecycle 반영
- 관련 테스트 추가
- ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- multi-worker parallel execution
- distributed scheduler
- worker autoscaling
- risk-based patch auto-apply
- full production orchestration layer

## 구체 작업 항목

- `ContainerizedWorkerRuntime` typed contract 정의
- static image ensure/build policy 정의
- worker runtime selection에서 container lane 추가
- timeout / cancellation / reclaim receipt 정리
- copy-in / copy-out (`docker cp`) air-gap policy 고정
- containerized worker proof CLI 추가
- container launch policy와 env/file isolation 정책 명시
- ownership normalization / orphan GC 구현
- replay/progress surface에 worker lifecycle 반영
- 테스트 추가
- ADR / implementation note 작성

## Acceptance Criteria

- containerized worker proof를 한 번 실행할 수 있다
- worker는 host source/ledger를 직접 mutate하지 못한다
- worker container는 `docker.sock` / privileged lane 없이 least-privilege로 실행된다
- copy-in / copy-out은 `docker cp` 기반 air-gap 경로를 사용한다
- copied-out files are ownership-normalized before intake reads them
- timeout / cancel / crash가 typed receipt로 회수된다
- stale/orphan worker containers are garbage-collected deterministically in the proof lane
- patch / artifact / receipt contract는 Step 12와 동일하게 유지된다
- founder/operator surface에서 worker lifecycle을 읽을 수 있다
- 테스트가 통과한다

## 리스크 / 메모

- `RISK-0027`을 이번 단계의 핵심 closure 대상으로 둡니다
- `RISK-0021`은 execution cancellation semantics 측면에서 추가 완화가 필요합니다
- `RISK-0022` multi-worker approval concurrency는 아직 범위 밖입니다
- container runtime을 올리더라도 control plane은 runtime-specific error를 직접 알지 않도록 seam을 유지해야 합니다
- `RISK-0030` docker socket / privileged escape
- `RISK-0031` ownership mismatch on copied-out artifacts
- `RISK-0032` orphan container leakage

## 연결 문서

- `docs/issues/STEP_12_EXECUTION_PLANE_EPIC.md`
- `docs/issues/STEP_12B_ISOLATED_WORKER_PROOF.md`
- `docs/issues/STEP_12C_PATCH_INTAKE_REVIEW_GATE.md`
- `docs/risk-register/entries/2026-04-17-lack-of-os-level-worker-isolation.md`
- `docs/risk-register/entries/2026-04-17-provider-cancellation-orphan.md`

## 기대 결과

Step 13이 끝나면 V2_SPRING은

- “계약만 있는 execution plane”
에서
- “실제 더 넓은 worker autonomy를 열 수 있는 execution plane”

으로 한 단계 올라가 있어야 합니다.
