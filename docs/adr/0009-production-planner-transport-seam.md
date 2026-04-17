# ADR 0009: Production Planner Transport Seam

## 상태

Accepted

## 배경

Step 10-a는 scripted transport로 planner slot을 증명했고, Step 10-b는 founder
reply lane을 완성했습니다.

이후 남은 간극은 production 현실이었습니다.

- 실제 network latency
- provider별 structured-output 동작
- token accounting
- retry / timeout / cancellation 처리
- sanitization과 bounded context windowing

실제 LLM을 planner core에 직접 연결하면 provider 예외와 SDK semantics가
control plane 경계를 넘어 새어나오게 됩니다.

## 결정

provider-agnostic한 `StructuredPlannerTransport` seam을 도입하고,
provider-specific behavior는 adapter edge에만 둡니다.

첫 번째 production 구현은 **OpenAI-first**이지만, core는 OpenAI-shaped가
아닙니다.

규칙:

- planner core는 `StructuredTransportResponse`만 상대합니다
- provider SDK exception은 내부 typed transport error로 번역됩니다
- prompt body는 transport invocation 전에 sanitization됩니다
- raw prompt/response body는 기본적으로 저장하지 않고, prompt hash와
  transport telemetry만 기록합니다
- bounded context window가 너무 커지면 transport invocation 전에 prompt
  payload를 truncate합니다
- provider/network retry는 transport adapter 내부에서 처리하고,
  planner phase budget accounting과 분리합니다
- 두 번째 provider는 planner core type을 바꾸지 않고 같은 seam 뒤에 추가할 수
  있습니다
- local cancellation은 typed transport error로 정규화되며, silent drop이 아닌
  bounded orphan-risk audit evidence로 기록됩니다

## 결과

### 긍정적

- provider/network 불안정성이 planner core 밖에 머무름
- raw prompt body를 저장하지 않고도 transport telemetry를 replay 가능하게 남길
  수 있음
- 두 번째 provider를 추가해도 planner core type은 바꿀 필요가 없음
- single-provider-first 구현으로도 지금 필요한 production hardening을 충분히
  제공할 수 있음

### 부정적

- 첫 concrete adapter는 여전히 vendor-specific behavior를 가지고 있으므로
  lock-in을 계속 감시해야 함
- 다른 provider는 각자 translation layer와 policy tuning이 필요함
- foreground CLI handling만으로는 cancellation/orphan behavior가 완전히 해결되지 않음
- prompt truncation은 bounded cost/latency를 위해 completeness를 일부 희생할 수 있음

## 후속

- Step 10-c가 첫 번째 concrete OpenAI transport와 telemetry path를 구현한다
- 현재 seam은 OpenAI-style JSON schema transport와 Anthropic-style tool-use
  transport path 양쪽 테스트로 검증된다
- cancellation/orphan semantics는 여전히 before-scale 리스크로 남는다
