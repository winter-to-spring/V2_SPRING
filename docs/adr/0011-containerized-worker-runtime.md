# ADR-0011: Containerized Worker Runtime은 Static Image, Air-Gapped Copy-In/Out, Least-Privilege Launch Policy를 사용한다

## 상태

Accepted

## 배경

Step 12는 execution-plane contract를 strengthened soft isolation으로
증명했지만, 더 넓은 bypass-style worker 실행을 열기에는 충분하지 않았습니다.

`RISK-0027`을 닫으려면, 기존 execution-plane contract를 유지하면서도 실제
OS/container 수준의 격리를 가진 worker runtime이 필요했습니다.

- worker는 `patch / artifact / receipt`를 반환한다
- worker는 control-plane 상태를 직접 변경하지 않는다
- 최종 patch 적용 여부는 founder review가 계속 게이트를 잡는다

## 결정

V2_SPRING은 아래 제약을 가진 containerized worker proof lane을 도입합니다.

1. 먼저 하나의 static worker image를 사용한다
2. workspace는 live host mount가 아니라 `docker cp` copy-in / copy-out으로
   전달한다
3. least-privilege container launch policy를 강제한다
   - Docker socket 노출 금지
   - `--privileged` 금지
   - 기본적으로 네트워크 차단
   - `cap-drop ALL`
   - `no-new-privileges`
4. copy-out된 파일은 intake 전에 host에서 ownership normalization을 거친다
5. proof-lane container는 deterministic label, timeout reclaim, startup
   garbage collection을 사용한다

## 결과

### 긍정적

- containerized worker 실행이 Step 12-b보다 실질적으로 더 안전해짐
- copy-in / copy-out 방식이 host workspace mutation 경계를 명확히 함
- patch와 receipt artifact가 계속 source of truth가 되므로 replay 결정론이 유지됨
- dynamic build pipeline 없이도 proof lane을 테스트할 수 있음

### 부정적

- 첫 runtime은 하나의 static image만 쓰므로 tool 다양성이 의도적으로 제한됨
- copy-in / copy-out은 live mount보다 느림
- container launch policy는 soft isolation보다 운영 복잡도가 높음

## 기각한 대안

### Live host volume mount

첫 proof에서는 host mutation semantics를 흐리고 isolation boundary를 약하게
만들기 때문에 기각했습니다.

### Dynamic image building

runtime contract 자체를 증명하는 데 image-pipeline 복잡도까지는 필요 없기
때문에 이 단계에서는 기각했습니다.

### Docker socket 또는 privileged helper

Step 13의 목적 자체를 host escape path로 무너뜨리기 때문에 기각했습니다.

## 관련 리스크

- `RISK-0027`
- `RISK-0030`
- `RISK-0031`
- `RISK-0032`

## 관련 노트

- `docs/implementation-notes/STEP_13_CONTAINERIZED_WORKER_RUNTIME.md`
