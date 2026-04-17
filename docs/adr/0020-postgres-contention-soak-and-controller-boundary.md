# ADR 0020: Postgres Contention Soak과 Controller Boundary

## 상태

Accepted

## 배경

Step 21은 V2_SPRING이 migration-controlled startup을 통해 PostgreSQL 위에서
부팅될 수 있음을 증명했습니다.

이건 필요조건이었지만, 더 건강한 multi-writer 미래를 열기 위한 충분조건은
아니었습니다. 다음 질문은 구조가 아니라 운영에 관한 것이었습니다.

- claim / renew / reclaim hot path가 실제 lock contention을 견딜 수 있는가?
- founder/operator tooling은 pool pressure와 lock pressure를 구분해 볼 수 있는가?
- 그 과정에서도 controller-owned DB trust boundary를 유지할 수 있는가?

## 결정

아래 Step 22 규칙을 채택합니다.

1. DB ownership은 controller-mediated로 유지한다. worker는 Postgres credential을
   직접 얻지 못한다.
2. Postgres diagnostics는 private operator script가 아니라 1급 `doctor`
   surface가 된다.
3. claim mutation hot path는 더 일관된 locking order로 수렴한다.
   - run row 먼저
   - claim row 나중
4. live PostgreSQL contention smoke harness를 storage verification의 일부로 둔다.
5. deadlock 회피는 단순 성능 문제가 아니라 correctness concern으로 취급한다.

## 결과

### 긍정적

- founder/operator tooling이 live lock waiting과 pool pressure를 볼 수 있다
- Postgres contention을 우연히가 아니라 의도적으로 검증할 수 있다
- controller-owned DB access를 운영적으로 설명하고 방어하기 쉬워진다
- Step 22가 `RISK-0058`을 실제로 줄이는 concrete burn-down path가 된다

### 부정적

- storage layer에 더 많은 diagnostic-specific code가 들어간다
- doctor surface는 bootstrap state뿐 아니라 runtime state도 보고하므로 더 복잡해진다
- connection pressure와 controller throughput은 여전히 후속 하드닝이 필요하다

## 후속

- 더 넓은 contention/load envelope가 증명될 때까지 `RISK-0055`, `RISK-0057`은
  mitigating 상태로 유지한다
- controller throughput이 더 잘 bounded될 때까지 `RISK-0061`도 mitigating으로 둔다
- `RISK-0059`, `RISK-0060`은 scale-oriented storage tuning 작업 전까지 defer한다
