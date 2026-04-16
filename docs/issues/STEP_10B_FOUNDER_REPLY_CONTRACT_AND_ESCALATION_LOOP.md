# [코어] Step 10-b - Founder reply contract and hint-first escalation loop

## 배경 / 문제

Step 10-a에서 planner는 이제 합법적으로 `EscalationProposal`을 제출할 수
있습니다. 하지만 founder가 그 escalation에 어떤 형식으로 답하는지,
그 답이 planner에게 어떻게 되먹이는지는 아직 계약이 없습니다.

이 단계가 없으면:
- founder reply가 단순 텍스트 힌트인지 강제 override인지 모호해지고
- planner가 escalation만 반복하는 thrash가 생기고
- human-in-the-loop semantics가 다시 자연어 감에 의존하게 됩니다

## 이번 단계의 목적

1. founder reply를 typed / replayable contract로 고정합니다.
2. **hint-first / override-available** 정책을 실제 상태 전이와 연결합니다.
3. escalation 이후 planner 재진입 루프를 bounded하게 만듭니다.
4. founder reply ambiguity와 premature escalation 리스크를 줄입니다.

## 구현 범위

- founder reply typed model
- reply kind 구분
  - `hint`
  - `override`
  - `reject`
- hint payload와 override payload를 분리한 union contract
- founder reply는 **current snapshot hash**가 아니라
  **target escalation id / founder intervention target**에 묶어 검증
- escalation replay linkage
- repeated escalation throttle or cooldown 1차 정책
- planner 재진입 시 founder hint를 bounded context에 주입하는 경로
- CLI proof path for founder replies
- 관련 ADR / implementation note / risk register 반영

## 이번 단계의 핵심 결정

1. **Override는 bounded override로 제한**
- founder override는 현재 `Legal Actions` 안에 있는 액션만 강제할 수 있습니다
- God mode는 열지 않습니다
- 룰을 깨는 예외 상황은 별도 운영 경로에서 다룹니다

2. **Reject는 억지 action 선택을 강요하지 않음**
- founder가 escalation을 reject했다고 해서 planner가 아무 action이나 찍게 만들지 않습니다
- reject는 현재 founder-help lane을 닫고, 필요하면 현재 planner phase를
  `exhausted` 또는 동등한 bounded stopped 상태로 보냅니다

3. **Escalation quota는 시간 기반이 아니라 phase-state 기반**
- 시간 기반 cooldown은 결정론과 replayability를 해칩니다
- 그래서 `per-phase hint quota` 또는 상태 기반 quota로 갑니다
- 1차 정책은 **phase당 founder hint 최대 2회**

4. **Founder intervention은 별도 typed intervention 기록으로 남김**
- override / hint / reject는 모두 replayable founder intervention event로 남깁니다
- 특히 override는 다음 planner context에
  "founder가 직접 개입해 액션을 밀었다"는 요약이 들어가야 합니다

5. **Founder reply context는 bounded window만 유지**
- 과거 founder replies 전부를 planner에 먹이지 않습니다
- latest active reply chain 또는 최근 2개 intervention만 context에 유지합니다

6. **Escalation quota 초과는 illegal rejection이 아니라 bounded exhaustion으로 처리**
- 같은 phase 안에서 founder hint quota를 초과한 추가 escalation이 들어오면,
  시스템은 그 escalation attempt를 기록한 뒤 현재 founder-help lane을
  `exhausted` 또는 동등한 bounded stopped 상태로 전이합니다
- 단순 `illegal`로만 튕기지 않습니다

7. **Founder hint는 auto-approve를 부여하지 않음**
- founder가 `hint`를 줬다고 해서 그 다음 planner proposal이 자동 승인되지는 않습니다
- hint 이후 planner가 낸 새 proposal은 여전히 기존 legality / governance 경로를 탑니다
- founder가 직접 실행을 밀고 싶을 때만 `override`를 사용합니다

8. **Founder override는 별도 founder-driven execution path로 기록**
- override는 planner proposal을 흉내 내는 것이 아니라
  `founder intervention`이 작성한 직접 개입 이벤트로 남겨야 합니다
- 다만 실행 자체는 기존 bounded execution / legal action 파이프라인에 연결되어야 합니다

## 이번 단계에서 하지 않는 것

- production provider hardening
- background worker 자동 루프
- semantic duplicate 고도화 전체
- founder UI

## 리스크 게이트

- `RISK-0016` premature escalation thrash
- `RISK-0017` founder reply contract ambiguity
- `RISK-0018` founder reply CLI ergonomics and operator typo risk

추가로 주의할 점:
- planner가 어려운 상황에서 너무 쉽게 escalation으로 도망가지 않도록
  escalation policy를 prompt와 시스템 계약 양쪽에서 제한해야 합니다
- founder hint는 단순 텍스트가 아니라 가능한 한
  `help_kind + requested_help + reply_kind` 형태로 구조화되어야 합니다
- hint를 줬는데 planner가 다시 escalation을 던질 수 있으므로,
  같은 phase 안에서는 escalation quota를 둬야 합니다
- override 이후에는 planner가 인과관계를 잃지 않도록
  founder intervention summary를 다음 context에 주입해야 합니다
- founder hint 이후 planner가 낸 proposal을 자동 승인하면
  hint와 override의 의미 차이가 흐려지므로, auto-approve는 열지 않습니다

## Acceptance Criteria

- founder reply가 typed / replayable하다
- hint와 override가 명확히 구분된다
- escalation 이후 재진입 경로가 deterministic하다
- planner는 founder hint를 bounded stateful context의 일부로 받는다
- repeated escalation에 대한 **state-based quota / throttle**이 존재한다
- founder reject는 planner에게 억지 action 선택을 강요하지 않는다
- founder override는 bounded override로만 동작한다
- founder intervention은 다음 planner context와 replay에 연결된다
- escalation quota 초과는 explicit bounded exhaustion으로 기록된다
- founder hint 이후의 planner proposal은 기존 approval / governance 규칙을 유지한다
- CLI에서 founder reply와 이후 planner 재진입을 proof할 수 있다

## 메모

- 기본 경로는 **hint-first**입니다
- override는 가능하지만 예외 경로로 제한합니다
- planner가 모를 때 아무 action이나 찍지 않고 escalation할 수 있어야 하지만,
  `blocking_reason`, `requested_help`, `analysis_summary` 없이 도망가서는 안 됩니다
- 이번 단계에서는 CLI 사용성을 위해 긴 자유 JSON 입력을 강제하기보다,
  가능한 한 짧은 enum + text 조합으로 founder reply를 받는 방향이 좋습니다
