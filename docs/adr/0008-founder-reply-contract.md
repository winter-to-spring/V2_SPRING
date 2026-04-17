# ADR 0008: Founder Reply 계약

## 상태

Accepted

## 배경

Step 10-a는 bounded planner output으로 `EscalationProposal`을 도입했습니다.

그 결과 새로운 공백이 생겼습니다.

- founder는 planner escalation을 받을 수 있게 되었지만
- founder의 응답 자체는 아직 typed되지 않았고
- hint, override, reject가 다음에 정확히 무엇을 하게 만드는지도 결정되지 않았습니다

founder reply contract가 없으면, human-in-the-loop lane은 다시 free-form chat
semantics로 돌아가고 replay의 의미도 약해집니다.

## 결정

founder reply를 세 가지 bounded response kind를 가진 discriminated union으로
표준화합니다.

1. `hint`
2. `override`
3. `reject`

추가 규칙:

- founder reply는 현재 snapshot hash가 아니라 **target escalation observation id**
  에 묶입니다
- `override`는 **bounded override**이며, 현재 legal-actions set 안에 있는 action만
  선택할 수 있습니다
- `reject`는 planner에게 다시 추측하게 하지 않습니다. 현재 founder-help lane을
  닫고 current planner phase를 exhausted 상태로 보냅니다
- `hint`는 다음 planner proposal을 auto-approve하지 않습니다. planner는 다시
  normal legality / governance path를 통과해야 합니다
- founder hint ping-pong는 **phase-scoped quota**로 bounded됩니다. 현재 정책은
  다음 escalation attempt가 phase를 exhausted시키기 전까지 founder hint를 최대
  두 번 허용합니다
- founder intervention은 replay 가능한 founder-specific record로 저장되며, 다음
  planner context window에 요약되어 다시 주입됩니다

## 결과

### 긍정적

- founder intervention이 명시적이고 replay 가능하며 machine-readable해짐
- planner/founder handoff가 모호한 자유 텍스트에만 의존하지 않게 됨
- bounded override가 god mode를 열지 않고 legality guarantee를 보존함
- reject semantics가 failed founder-help 요청 뒤 planner가 임의 action을
  hallucinate하는 것을 막음

### 부정적

- CLI 표면이 더 구조화되어 사용감이 조금 무거워짐
- founder intervention policy를 planner governance policy와 계속 맞춰야 함
- CLI 타이핑 마찰을 줄이려면 이후 richer founder surface가 여전히 필요함

## 후속

- Step 10-b가 founder reply contract와 proof CLI를 구현한다
- Step 10-c가 production transport, prompt policy, richer founder feedback
  handling을 하드닝한다
