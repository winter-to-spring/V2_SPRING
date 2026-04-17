# ADR 0015: Lease-aware Execution Claim과 Pessimistic Reclaim

## 상태

Accepted

## 배경

Step 16 시점에서 V2_SPRING은 점점 더 강한 worker를 dispatch할 수 있었지만,
in-flight execution에 대한 typed ownership 모델은 아직 없었습니다.

그로 인해 세 가지 공백이 남아 있었습니다.

- 여러 worker가 shared claim model 없이 같은 run을 두고 경합할 수 있었다
- approval-sensitive mutation이 live execution과 race를 일으킬 수 있었다
- expired/orphan execution은 명시적 reclaim과 audit 없이는 여전히 애매했다

다음 capability slice는 아래에 답해야 했습니다.

- 지금 이 execution lane의 주인은 누구인가
- 그 ownership은 언제까지 유효한가
- ownership이 만료되거나 orphan이 되면 무슨 일이 일어나는가

## 결정

control-plane layer에 lease-aware execution claim model을 도입합니다.

이 모델은 아래를 포함합니다.

- run당 하나의 execution claim
- typed claim lifecycle
  - `ACTIVE`
  - `RELEASED`
  - `RECLAIMED`
  - `EXPIRED`는 향후 용도로 예약
- lease metadata
  - owner
  - runtime
  - lease token
  - acquired / heartbeat / expiry timestamp
- approval-sensitive mutation lane에 lease-aware guard 추가
- snapshot, progress surface, replay, audit에서 claim lifecycle 가시화

또한 **pessimistic reclaim** 정책을 채택합니다.

- lease TTL에는 작은 slack window가 포함된다
- expiry가 관측되는 순간 이전 owner는 더 이상 신뢰하지 않는다
- reclaim은 ownership을 다시 열기 전에 runtime-specific hard fencing을 시도한다
- reclaim 이후 late result는 받아들이지 않는다

## 결과

### 긍정적

- competing dispatch가 implicit race가 아니라 typed refusal이 된다
- approval/founder mutation이 live execution과 조용히 interleave되지 않는다
- expired claim은 reclaim 가능하고 founder-visible해진다
- reclaim outcome이 명시적인 audit evidence로 기록된다

### 부정적

- lease bookkeeping이 runtime/state 복잡도를 높인다
- TTL 설계 자체가 하나의 governance surface가 된다
- 더 넓은 multi-worker scale 전에는 stronger atomic claim semantics와 heartbeat
  policy가 추가로 필요할 수 있다

## 후속

- Step 17은 현재 single-node/current-runtime concurrency gap을 닫는다
- stronger atomic claim semantics는 `RISK-0047`로 계속 추적한다
- longer-lived/adaptive lease policy는 `RISK-0046`으로 계속 추적한다
- reclaim side-effect fencing은 `RISK-0048`로 계속 추적한다
