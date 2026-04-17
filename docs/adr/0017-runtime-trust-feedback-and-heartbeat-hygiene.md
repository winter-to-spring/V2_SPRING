# ADR 0017: Runtime Trust Feedback과 Heartbeat Hygiene

## 상태

Accepted

## 배경

Step 18은 claim layer에서 lease ownership과 fenced reclaim을 닫았지만, 두 가지
운영 공백이 남아 있었습니다.

- static worker manifest가 실제 runtime behavior와 어긋날 수 있었다
- worker 수가 늘어날수록 lease renewal이 불필요한 write churn을 만들 수 있었다

V2_SPRING은 기본 경로를 결정론적이고 저렴하게 유지하면서도, 실제 runtime
evidence가 선언된 capability와 충돌할 때는 반응할 수 있어야 합니다.

## 결정

runtime trust layer와 tighter renewal hygiene를 아래 규칙으로 도입합니다.

1. containerized runtime trust는 ledger 안의 typed state로 중앙 저장한다
2. static manifest preflight는 기본 경로로 유지한다
3. runtime은 **3회 연속** capability mismatch가 발생한 뒤에야 dynamic
   preflight로 승격된다
4. dynamic preflight로 승격된 runtime은 **2회 성공**하면 다시 static-first
   모드로 돌아간다
5. lease renewal은 store/server time만을 진실의 원천으로 쓴다
6. renewal write는 minimum cadence window로 coalesce하여 모든 heartbeat 호출마다
   쓰지 않도록 한다

## 결과

### 긍정적

- runtime trust가 선언된 metadata만으로 결정되지 않게 된다
- noisy한 one-off failure 때문에 곧바로 expensive dynamic check로 가지 않는다
- healthy lease는 불필요한 renewal write를 피한다
- founder/operator surface에서 runtime trust degradation을 직접 확인할 수 있다

### 부정적

- runtime trust라는 작은 state machine을 추가로 관리해야 한다
- runtime은 dynamic preflight로 승격되기 전까지 몇 번 실패할 수 있다
- worker fleet이 커지면 heartbeat cadence를 계속 관찰해야 한다

## 후속

- `RISK-0051`은 networked 또는 side-effectful runtime이 열릴 때까지 defer한다
- explicit strike/recovery 규칙이 부족하다는 증거가 생길 때만 richer trust
  scoring을 재검토한다
