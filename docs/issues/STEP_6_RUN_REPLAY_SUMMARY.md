# [코어] Step 6 - Run history/replay summary + task/artifact linkage query CLI

## 배경 / 문제

Step 5까지 오면서 V2_SPRING은 CLI에서 다음을 직접 검증할 수 있게 됐습니다.

- run이 생성되는지
- approval이 실제로 걸리고 해제되는지
- bounded task 1개가 실제로 수행되는지
- artifact가 provenance와 hash를 포함해 남는지

이제 다음으로 자연스럽게 필요한 것은, **이 실행 흔적을 사람이 한 번에 다시 따라갈 수 있는 요약/재생 surface**입니다.

지금도 `run show`, `run events`, `task list`, `artifact list`를 각각 치면 조각은 볼 수 있습니다.
하지만 founder/operator 입장에서는 여전히 다음 질문에 답하기 번거롭습니다.

- 어떤 승인 이후 어떤 task가 실행됐지?
- 그 task는 어떤 decision을 근거로 움직였지?
- 어떤 artifact가 나왔고 어디에 남았지?
- 이 run은 지금 어떤 상태로 끝났지?
- 실패한 시도가 있었다면 최종 성공과 어떻게 구분하지?

Step 6은 이 조각들을 **조회 가능한 하나의 실행 서사**로 묶는 단계입니다.

---

## 이번 단계의 목적

1. `Run -> Approval -> Decision -> Task -> Artifact` 연결을 CLI에서 한 번에 따라갈 수 있게 합니다.
2. `run replay` 또는 이에 준하는 요약 명령으로 founder 검증 경험을 개선합니다.
3. task/artifact linkage를 더 직접적으로 조회할 수 있게 합니다.
4. 사람이 읽는 기본 출력과 기계가 읽는 JSON 출력을 분리합니다.
5. 실패 시도는 숨기지 않되, 기본 출력에서는 읽기 가능한 요약으로 다룹니다.

---

## 구현 범위

이번 단계에서는 아래 범위까지만 포함합니다.

- `v2-spring run replay <run-id>` 또는 동등한 run summary/replay CLI
- `pretty` / `json` 출력 포맷 지원
- approval / decision / task / artifact 관계를 요약해서 보여주는 읽기 전용 출력
- `task show <task-id>` 또는 동등한 task linkage 조회
- `artifact show <artifact-id>` 또는 동등한 artifact provenance / integrity 조회
- replay/summary 출력 포맷 정리
- 고정 쿼리 수를 유지하는 read model / query strategy
- 관련 테스트 추가
- implementation note / tracer bullet 문서 갱신

---

## 이번 단계에서 하지 않는 것

이번 단계에서는 아래는 하지 않습니다.

- full event sourcing viewer
- UI 대시보드
- multi-task orchestration
- LangGraph planner 연결
- CrewAI workforce 연결
- Redis coordination 확장
- approval timeout / watchdog
- artifact versioning
- 검색/필터가 풍부한 운영 콘솔
- 대규모 run에 대한 streaming replay

즉 이번 단계는 **실행 흔적을 더 읽기 쉽게 만드는 최소 읽기 표면**에 집중합니다.

---

## 출력 정책

### 기본 출력 (`pretty`)
- 사람 친화적인 요약 중심
- 현재 상태, 주 경로(success path), 연결된 task/artifact를 먼저 보여줌
- 실패 시도는 요약된 section으로만 보여줌

### JSON 출력
- 자동화/스크립트/후속 UI 어댑터용
- 구조화된 run/task/artifact linkage 전체를 그대로 제공

---

## 실패 시도 표시 정책

- 실패 시도는 삭제하거나 숨기지 않습니다.
- 기본 출력에서는 “몇 번 실패했고, 마지막으로 왜 실패했는지” 정도의 요약을 보여줍니다.
- JSON 출력이나 detail query에서는 실패 시도를 더 자세히 확인할 수 있어야 합니다.

---

## 구체 작업 항목

- [ ] `run replay` 또는 동등한 요약 CLI 추가
- [ ] `--format pretty|json` 지원
- [ ] `--verbose` 또는 동등한 상세 출력 지원
- [ ] run 단위로 approval / decision / task / artifact 관계를 한 번에 묶어 출력
- [ ] `task show <task-id>` 또는 동등한 task detail 조회 추가
- [ ] `artifact show <artifact-id>` 또는 동등한 artifact provenance / integrity 조회 추가
- [ ] task와 artifact 사이의 linkage가 출력에 드러나게 정리
- [ ] final run status와 주요 branch point가 함께 보이게 정리
- [ ] 실패 시도를 기본 출력에서 요약 section으로 표시
- [ ] 고정 쿼리 수를 유지하는 read model / query strategy 반영
- [ ] 관련 테스트 추가
- [ ] implementation note 작성
- [ ] tracer bullet 문서 갱신

---

## Acceptance Criteria

- founder가 CLI만으로 run의 전체 실행 흔적을 더 쉽게 따라갈 수 있다.
- `approval -> decision -> task -> artifact` 흐름이 run 단위 출력에서 확인된다.
- task 단위로 어떤 artifact를 남겼는지 역추적 가능하다.
- artifact 단위로 어떤 run/task/decision에서 나왔는지 역추적 가능하다.
- artifact 파일의 존재 여부와 hash 일치 여부를 확인할 수 있다.
- replay 출력이 artifact 유실/변조와 주요 state-vs-ledger 불일치를 consistency warning으로 보여준다.
- 기본 출력은 읽기 쉬운 요약을 제공하고, JSON 출력은 구조화된 전체 linkage를 제공한다.
- 실패 시도는 삭제되지 않고, 기본 출력에서는 요약된 형태로 노출된다.
- 현재 상태와 최종 상태가 요약 출력에서 분명하다.
- 테스트가 통과한다.
- 문서와 구현이 일치한다.

---

## 리스크 / 메모

- 출력이 너무 길어지면 다시 읽기 어려워질 수 있으므로, “완전한 raw dump”가 아니라 founder/operator가 읽을 수 있는 summary 우선이 좋습니다.
- task/artifact linkage가 출력에만 있고 데이터 모델이 약하면 추후 planner 단계에서 다시 흔들릴 수 있습니다.
- 현재는 `timestamp + id` 정렬로 충분하지만, 이후 concurrent worker 단계에서는 논리적 sequence가 필요할 수 있습니다.
- 이번 단계는 replay engine 전체가 아니라, **replay 가능한 최소 읽기 표면**을 만드는 단계여야 합니다.

---

## 연결 문서 / ADR

- `docs/specs/TRACER_BULLET.md`
- `docs/verification/FOUNDER_VERIFICATION_REQUIREMENTS.md`
- `docs/adr/0003-core-state-model.md`
- `docs/adr/0005-founder-verification-surface.md`

Step 6이 끝나면 다음으로는 planner 가능한 action selection 또는 richer execution receipt 쪽으로 더 자연스럽게 이어갈 수 있어야 합니다.
