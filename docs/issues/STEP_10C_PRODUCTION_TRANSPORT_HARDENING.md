# [코어] Step 10-c - Production transport hardening for the planner adapter

## 배경 / 문제

Step 10-a가 scripted proof transport로 adapter 계약과 governance slot을
검증했다면, Step 10-c는 실제 production LLM provider를 꽂았을 때
발생하는 **네트워크, 비용, 컨텍스트, 관측성, sanitization** 문제를
닫는 단계입니다.

이 단계가 없으면 production에서 바로:
- provider latency / timeout / orphan invocation
- 429 / 5xx / retry policy drift
- token leak
- context overflow
- prompt / failure report sanitization 누락
- premature escalation 증폭
같은 문제가 터질 수 있습니다.

## 이번 단계의 목적

1. scripted transport를 넘어 실제 provider transport를 안전하게 붙입니다.
2. production 경로에서도 structured outputs enforcement를 유지합니다.
3. provider-level observability와 cost telemetry를 확보합니다.
4. bounded stateful planner가 raw ledger 대신
   **Structured Failure Report**와 bounded context만 받도록 강제합니다.

## 구현 범위

- production planner transport adapter
- **single-provider-first implementation + provider-agnostic seam**
- structured outputs / schema-enforced output 경로
- timeout / cancellation / bounded retry / backoff 정책
- token usage metadata capture
- context window truncation / sliding policy
- sanitization and payload hygiene hardening
- richer adapter telemetry
- raw prompt/response capture policy
- 관련 ADR / implementation note / risk register 반영

## 이번 단계에서 하지 않는 것

- full autonomous workforce loop
- founder UI
- distributed coordination 전체
- multi-provider routing 최적화 전체

## 리스크 게이트

- `RISK-0013` execution failure loop escape
- `RISK-0015` structured failure report fidelity
- `RISK-0016` premature escalation thrash
- `RISK-0017` founder reply contract ambiguity

추가 production 리스크:
- network timeout / cancellation이 orphan cost로 이어질 수 있음
- 429 / 5xx는 planner logic failure가 아니라 provider/network failure일 수 있음
- token usage를 남기지 않으면 비용 누수를 추적할 수 없음
- context overflow는 hard error가 아니라 사전 truncation 정책으로 막아야 함
- raw prompt/response를 무분별하게 저장하면 민감 정보가 새나갈 수 있음

## 핵심 설계 결정

- LLM에는 raw ledger 전체를 넣지 않습니다
- planner 입력은 **Structured Failure Report + bounded recent attempts + snapshot**만 사용합니다
- output parsing은 자유 텍스트 후처리가 아니라
  **schema-enforced structured outputs**를 기본 경로로 사용합니다
- provider 구현은 먼저 하나로 닫되, 내부 seam은 provider-agnostic하게 유지합니다
- `stale`은 main planner budget과 분리된 stale quota를 사용합니다

## Acceptance Criteria

- production transport가 typed adapter contract를 지킨다
- parse/schema mismatch가 bounded하게 처리된다
- timeout / retry / cancellation 정책이 문서와 코드에 존재한다
- token usage metadata가 ledger 또는 동등한 audit surface에 남는다
- context window truncation 정책이 존재한다
- 민감 정보 노출 없이 adapter observability가 확보된다
- planner-facing audit hygiene 리스크가 완화된다

## 메모

- `with_retry()`류 재시도는 provider/network failure 경로에만 쓰고,
  planner logic failure와 섞지 않습니다
- structured failure report의 fidelity가 낮으면 planner 품질도 같이 낮아지므로
  production hardening과 함께 failure report 품질 검토가 필요합니다
