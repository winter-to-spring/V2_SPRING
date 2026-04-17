# ADR 0018: Snapshot Freshness와 Cancellation Reconciliation

## 상태

Accepted

## 배경

Step 19 시점에도 현재 local CLI substrate에는 두 가지 운영 무결성 공백이
남아 있었습니다.

- founder/operator mutation flow가 inspection 이후 stale해진 snapshot을 기반으로
  여전히 동작할 수 있었다
- local planner cancellation은 typed되었지만, audit trail이 interrupt event에서
  멈추어 bounded reconciliation outcome을 남기지 못했다

V2_SPRING은 outdated state를 기반으로 한 founder/operator action이 loud failure로
끝나게 해야 하고, local cancellation도 silent "아마 취소됨"이 아니라
ledger-visible한 결정론적 종료 상태를 가져야 합니다.

## 결정

Step 20을 아래 규칙으로 하드닝합니다.

1. `RunSnapshotView`는 기존 `state_hash` 외에 `freshness_generation`도 가진다
2. inspected state에 의존하는 founder/operator mutation lane은 명시적 freshness
   anchor를 받아야 한다
3. `task dispatch`, `patch approve`, `patch reject`는 stale anchor를
   `SnapshotFreshnessRefusalView`로 거부한다
4. progress와 patch-review surface는 founder가 같은 mutation command를 안전하게
   replay할 수 있도록 freshness anchor를 보여준다
5. local planner cancellation은 두 개의 audit event로 기록된다
   - cancellation intent
   - local reconciliation / bounded orphan-risk finalization

## 결과

### 긍정적

- stale founder/operator action이 state drift 뒤에 조용히 mutation을 일으키지 않음
- progress/review surface가 기대하는 freshness contract를 정확히 노출함
- local cancellation이 이후 진단에 더 명확한 replay trail을 남김
- Step 20은 DB migration 없이도 current-scope snapshot freshness gap을 닫음

### 부정적

- mutation command가 약간의 추가 anchor metadata를 가져야 함
- stale founder action이 더 명시적으로 실패하므로 초기에 더 엄격하게 느껴질 수 있음
- cancellation semantics는 더 명확해졌지만, provider-side orphan spend는 여전히
  before-scale 리스크로 남음

## 후속

- planner cancellation이 foreground CLI를 넘어 stronger provider-side
  reconciliation을 갖기 전까지 `RISK-0021`은 계속 열어둔다
- Postgres migration이 시작되면 더 강한 transactional freshness guarantee를
  다시 검토한다
