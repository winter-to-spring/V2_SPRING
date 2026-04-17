# ADR 0007: 구조화된 Planner Decision Output 계약

## 배경

Step 10은 실제 planner adapter가 V2_SPRING control plane에 처음 진입하는
지점입니다.

Step 9까지 이미 갖춘 것은 아래와 같습니다.

- typed run/task/approval/task-artifact 상태
- replay 가능한 planner attempt
- bounded planner phase budget
- deterministic legal-action evaluation

다음 리스크는 단순히 "LLM이 답할 수 있는가?"가 아니라, "LLM이 V1처럼
질식할 정도로 경직되지 않으면서도 governance 모델을 벗어나지 않고 답할 수
있는가?"였습니다.

동시에 피해야 할 실패는 두 가지였습니다.

1. parse, govern, audit가 어려운 free-form text output
2. escalate해야 할 상황에서도 action 하나를 억지로 찍게 만드는 지나치게
   좁은 schema

## 결정

Step 10은 **structured, discriminated-union planner output contract**를
채택합니다.

planner adapter는 아래 두 legal proposal shape 중 하나를 반환합니다.

- `ActionProposal`
- `EscalationProposal`

두 proposal 모두 schema validation을 거치며, 명시적 `kind` discriminator로
선택됩니다.

## 왜 Structured Output인가

V2_SPRING이 planner slot에 요구하는 것은 아래와 같습니다.

- machine-readable
- replayable
- governance에 bounded됨
- parser drift에 강함

free-form text는 parser loop와 숨은 planner drift를 너무 쉽게 허용합니다.

따라서 Step 10은 structured output을 기본 경로로 유지합니다.

## ActionProposal vs EscalationProposal

`ActionProposal`은 이미 deterministic legal-action engine 안에 존재하는
정상 next move를 표현합니다.

`EscalationProposal`은 planner가 안전하게 next action을 고를 수 없을 때,
founder-facing governance request를 표현합니다.

이 분리는 domain purity를 지켜줍니다.

- legal-action engine은 execution-domain component로 남음
- escalation은 governance-domain component로 남음

우리는 escalation을 일반 action enum 안에 넣지 않습니다.

## Reasoning Summary 정책

planner는 여전히 자기 판단을 설명할 수 있어야 합니다.

하지만 V2_SPRING은 raw chain-of-thought를 저장하지 않습니다.

대신 이 계약은 아래와 같은 bounded reasoning metadata를 요구합니다.

- `analysis_summary`
- `confidence`
- `blocking_reason`
- `requested_help`

이렇게 하면 ledger를 chain-of-thought dump로 만들지 않으면서도 관측 가능성을
유지할 수 있습니다.

`confidence`는 safety authority가 아니라 observational signal로 취급합니다.
