# ADR 0012: Container Runtime Provenance와 Guardrail

## 상태

Accepted

## 배경

Step 13은 containerized worker runtime을 도입했지만, 세 가지 신뢰 공백이
남아 있었습니다.

- mutable image tag가 deterministic replay를 약하게 만들었다
- log 수집이 여전히 root cause를 가리거나 host에 압박을 줄 수 있었다
- container capability claim을 shared manifest와 대조하지 않았다

Step 14는 dispatch path에 live registry 의존성을 넣지 않으면서 이 공백을
닫습니다.

## 결정

아래 runtime provenance / guardrail 정책을 채택합니다.

1. Container runtime metadata는 repo-managed registry artifact에 저장한다
   - 현재 경로: `infra/worker_manifest.json`
   - dispatch/preflight는 live registry query에 의존하면 안 된다
2. worker base image는 immutable digest로 pin한다
3. receipt에는 runtime provenance를 기록한다
   - image tag
   - resolved local image digest
   - metadata registry path
   - metadata registry schema version
   - metadata registry checksum
4. log hygiene는 bounded하면서 diagnostic-first여야 한다
   - tail-only 대신 sandwich capture(`head + tail`)를 사용한다
   - oversized log는 전체 raw copy-out 대신 bounded evidence를 반환한다
5. capability preflight는 static-first, selective dynamic escalation으로 간다
   - static manifest check는 항상 적용한다
   - 일부 lane만 lightweight dynamic admission check를 수행할 수 있다
6. compatibility mismatch는 vague crash가 아니라 typed refusal로 처리한다

## 결과

### 긍정적

- replay가 runtime identity를 더 정확히 구분할 수 있다
- 외부 registry가 죽어도 dispatch 가용성이 유지된다
- startup failure를 놓치지 않으면서도 operator diagnostics를 bounded하게
  유지할 수 있다
- capability mismatch가 혼란스러운 crash가 아니라 governance된 outcome이 된다

### 부정적

- metadata registry가 새로운 control-plane artifact가 된다
- routing과 execution이 환경 간 manifest 일관성에 의존하게 된다
- selective dynamic check는 소량의 runtime overhead를 추가한다

## 후속

- `RISK-0036` image bloat / cold-pull latency는 계속 열어둔다
- `RISK-0039`는 더 많은 observed-runtime trust signal이 쌓일 때까지 mitigating
  상태로 유지한다
