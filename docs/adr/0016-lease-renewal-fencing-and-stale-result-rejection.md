# ADR 0016: Lease Renewal, Fencing Token, 그리고 Stale Result Rejection

## 상태

Accepted

## 배경

Step 17은 lease-aware execution claim을 도입했지만, 세 가지 하드닝 공백이
남아 있었습니다.

- bounded TTL만으로는 longer-running work를 굶기거나 premature reclaim을
  일으킬 수 있었다
- claim acquisition은 단순 check-then-write보다 더 강한 atomic/CAS 성질이
  필요했다
- ownership이 바뀐 뒤 late worker result가 절대 받아들여지지 않도록 더 명확한
  fence가 필요했다

이 공백은 아래 리스크로 추적되었습니다.

- `RISK-0046`
- `RISK-0047`
- `RISK-0048`

## 결정

execution-claim model을 아래 세 규칙으로 하드닝합니다.

### 1. Thresholded lease renewal

worker는 active lease의 renewal을 요청할 수 있지만, 남은 TTL이 bounded threshold
아래로 내려왔을 때만 갱신됩니다.

- worker는 renewal intent만 보낸다
- `heartbeat_at`과 `expires_at`의 truth는 store가 가진다
- expiry 판단에 worker clock을 신뢰하지 않는다
- healthy lease는 불필요한 heartbeat write를 만들지 않는다

### 2. Version-gated atomic claim update

execution claim reacquire/update path는 claim `version`을 fencing token이자
compare-and-swap guard로 사용합니다.

- 각 run은 여전히 최대 하나의 claim row만 가진다
- insert conflict는 typed refusal로 처리된다
- 기존 row의 reacquire/renew는 expected version/token이 일치할 때만 성공한다

### 3. Fenced stale-result rejection

result submission은 현재 유효한 task claim token과 fencing token과 일치해야
합니다.

- reclaim되었거나 superseded된 worker는 accepted result를 떨어뜨릴 수 없다
- stale result는 typed ledger/audit evidence를 남긴다
- reclaim은 founder-visible한 pessimistic reclaim으로 유지된다

## 결과

### 긍정적

- longer-running bounded work가 하나의 고정 TTL에 매이지 않게 된다
- claim ownership이 단순 transaction ordering보다 강해진다
- reclaim 이후 late result를 결정론적으로 거부할 수 있다
- expiry 판단이 worker clock이 아니라 store/server time에 고정된다

### 부정적

- claim bookkeeping이 더 복잡해진다
- renew/reclaim path가 더 많은 ledger traffic을 만든다
- 더 큰 scale에서는 batching이나 smarter heartbeat policy가 여전히 필요할 수 있다
- external side-effect는 networked runtime 단계에서 따로 다뤄야 한다

## 후속

- `RISK-0046`, `RISK-0047`, `RISK-0048`은 현재 범위에서 해결된다
- `RISK-0050` clock drift는 store-time truth로 흡수되어 resolved로 기록된다
- `RISK-0049` heartbeat storm은 Before Scale follow-on 리스크로 남는다
- `RISK-0051` external side-effect ghost는 networked runtime 전까지 follow-on
  리스크로 남는다
