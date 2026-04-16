# [코어] Step 9 - Bounded replanning loop + planner attempt governance

## 배경 / 문제

Step 8까지 오면서 V2_SPRING은 이제 planner proposal contract를 갖게 되었습니다.

즉, founder는 CLI에서 다음을 직접 확인할 수 있습니다.

- 현재 run snapshot
- 현재 legal actions
- planner proposal이 legal한지 / stale한지
- accepted proposal이 Decision으로 남는지

하지만 아직 planner loop를 실제로 열기엔 중요한 빈틈이 남아 있습니다.

- planner가 stale/illegal proposal을 반복할 때 언제 멈춰야 하는지
- 동일 proposal을 반복 제출했을 때 어떻게 다뤄야 하는지
- rejection / invalid proposal 시도가 어떤 구조로 traceability를 가져야 하는지
- bounded replanning이 언제 human escalation으로 넘어가야 하는지

지금 이 상태에서 real planner adapter를 붙이면,
proposal contract는 있어도 **proposal governance**가 없어서 자율성이 쉽게 무한 루프나 token waste로 흐를 수 있습니다.

그래서 Step 9는 “더 똑똑한 planner”를 붙이는 단계가 아니라,
**planner가 bounded하게 여러 번 생각하고, 실패하고, 다시 제안하되, 반드시 멈출 줄 아는 틀**을 만드는 단계입니다.

이 단계는 현재 risk register 기준으로 `RISK-0008`을 직접 흡수하는 slice입니다.

이번 단계의 핵심 정책 결정은 다음과 같습니다.

- retry budget은 **Run 전체 공유 예산이 아니라 phase-scoped budget**으로 둡니다.
- 즉, 새로운 성공적인 state advancement가 일어나면 planner attempt budget은 다시 초기화될 수 있습니다.
- 대신 미래 전체 비용 보호를 위해 run-lifetime global cap을 얹을 여지는 남겨둡니다.

이유는 간단합니다.

- global budget만 쓰면 긴 run의 후반부에서 사소한 stale/illegal proposal 하나 때문에 전체가 너무 쉽게 exhausted 됩니다.
- phase budget은 상태 전진 단위로 bounded autonomy를 주기 때문에, 장기적인 복합 run에도 더 잘 맞습니다.

Step 9는 이 phase budget을 deterministic substrate에 먼저 고정하는 단계입니다.

---

## 이번 단계의 목적

이번 단계의 목적은 아래 6가지입니다.

1. planner attempt를 bounded loop로 정의합니다.
2. stale / illegal / duplicate proposal에 대한 deterministic governance를 정의합니다.
3. retry budget, stop condition, escalation condition을 명시적으로 고정합니다.
4. rejected/invalid proposal 시도를 replay 가능한 형태로 더 명확히 남깁니다.
5. founder가 CLI에서 planner attempt 흐름을 직접 확인할 수 있게 합니다.
6. 이후 real planner adapter가 이 governance를 그대로 따를 수 있게 준비합니다.

---

## 구현 범위

이번 이슈는 아래 범위까지만 포함합니다.

- planner attempt lifecycle 정의
- bounded replanning loop 규칙 정의
- planner attempt counter / retry budget 정의
- phase budget reset 규칙 정의
- stale proposal 처리 규칙 고정
- illegal proposal 처리 규칙 고정
- duplicate proposal / idempotency 정책 1차 정의
- escalation / exhaustion 조건 정의
- exhaustion 이후 founder-driven resume/recharge hook 정의
- 관련 ledger event 또는 structured trace 추가
- planner attempt inspection CLI 추가 또는 기존 CLI 확장
- 관련 테스트 추가
- ADR / 설계 문서 / implementation note 반영

---

## 이번 단계에서 하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- real LangGraph integration
- 실제 LLM 호출
- automatic execution chaining 전체
- CrewAI workforce 연결
- background worker
- distributed locking
- UI
- full autonomous end-to-end loop
- hiring / budget policy 전체

즉, 이번 단계는 **planner를 실제로 붙이기 전에 planner loop의 안전 장치와 실패 경계부터 고정하는 단계**입니다.

---

## 구체 작업 항목

- [ ] planner attempt lifecycle typed model 또는 equivalent trace 구조 정의
- [ ] retry budget / stop condition / escalation condition 정의
- [ ] phase-scoped budget reset 규칙 정의
- [ ] stale proposal 처리 정책 명시
- [ ] illegal proposal 처리 정책 명시
- [ ] duplicate proposal / idempotency policy 1차 정의
- [ ] stale / illegal / duplicate attempt outcome code 정의
- [ ] attempt / retry / exhausted / escalated trace 기록 구현
- [ ] founder resume / recharge hook 정책 정의
- [ ] founder가 CLI로 attempt 상태를 확인할 수 있게 surface 추가
- [ ] 기본 replay에서는 반복 실패를 요약하고, verbose에서 전체 attempt를 노출하는 정책 정의
- [ ] replay에서 proposal attempt 흐름이 읽히도록 연결
- [ ] 관련 테스트 추가
- [ ] ADR 작성 또는 갱신
- [ ] implementation note 작성

---

## Acceptance Criteria

- planner proposal은 무한히 반복되지 않는다.
- stale / illegal proposal에 대해 bounded한 처리 규칙이 존재한다.
- 동일 proposal 반복 제출에 대한 정책이 명시된다.
- duplicate transport retry와 duplicate cognitive retry가 구분된다.
- retry budget 소진 시 deterministic한 exhaustion 또는 escalation 결과가 존재한다.
- exhaustion 이후 founder가 재개 가능한 deterministic hook이 존재한다.
- proposal attempt / retry / exhaustion 이력이 ledger 또는 equivalent trace에 남는다.
- stale / illegal / duplicate / exhausted가 구조화된 outcome으로 구분된다.
- founder가 CLI에서 planner attempt 흐름을 직접 확인할 수 있다.
- real planner adapter를 붙이기 전 필요한 governance 경계가 문서로 고정된다.
- 테스트가 통과한다.
- 문서와 실제 구현이 일치한다.

---

## 리스크 / 메모

- retry budget이 너무 빡빡하면 planner 자율성이 죽습니다.
- 반대로 너무 느슨하면 bounded loop가 사실상 무한 루프가 됩니다.
- duplicate proposal policy를 늦게 정하면 나중에 decision trail이 오염될 수 있습니다.
- semantic duplicate는 deterministic substrate에서 완벽하게 잡기 어렵기 때문에, Step 9에서는 exact submission identity와 exact proposal fingerprint 중심으로 1차 정책을 고정합니다.
- rejection traceability가 약하면 replay는 있어도 root cause를 읽기 어렵습니다.
- 이번 단계는 planner intelligence가 아니라 **planner governance**를 다루는 단계입니다.

---

## 연결 문서 / ADR

- `docs/specs/TRACER_BULLET.md`
- `docs/implementation-notes/STEP_8_PLANNER_PROPOSAL_CONTRACT.md`
- `docs/adr/0004-deterministic-substrate.md`
- `docs/risk-register/entries/2026-04-16-planner-proposal-loop-control.md`
- `docs/risk-register/entries/2026-04-16-planner-audit-payload-hygiene.md`

이번 단계가 끝나면 다음으로는

- real planner adapter
- bounded execution chaining
- planner/replanner loop

를 훨씬 더 안전하게 올릴 수 있어야 합니다.
