# ADR-0010: Execution Plane Routing 정책

## 상태

Accepted

## 배경

Step 12는 execution plane을 엽니다. 이 시점부터 control plane은 어떤 task를
어떤 execution runtime이 처리할지 결정해야 합니다. 이때 runtime taxonomy가
planner prompt로 새면 안 되고, worker가 자기 lane을 스스로 고르게 해도 안
됩니다.

우리가 원하는 것은 아래와 같습니다.

- deterministic control-plane routing
- planner/runtime decoupling
- founder-visible routing rationale
- route가 legal하지 않거나 fulfillable하지 않을 때의 safe refusal
- 이후 isolated worker와 multi-runtime execution까지 자랄 수 있지만 opaque
  magic이 되지는 않는 좁은 seam

## 결정

우리는 명시적 dispatcher를 가진 **requirements-based routing**을 채택합니다.

### Planner 책임

planner는 runtime 이름이 아니라 **execution requirements**를 선언합니다.

예:

- `task_complexity`
- `needs_isolation`
- `requires_network`
- `needs_multi_file_context`
- `write_scope`
- `expected_output_kind`

planner는 `isolated_worker`, `crewai_team` 같은 concrete runtime identifier를
직접 내보내면 안 됩니다.

### Dispatcher 책임

runtime selection은 Python control plane이 맡습니다.

dispatcher는 아래를 수행해야 합니다.

- 과하게 부풀려진 requirement를 정규화한다
- founder/system capability ceiling을 강제한다
- 명시적 policy branch를 통해 requirement를 concrete runtime으로 매핑한다
- 안전한 runtime이 없을 때 typed refusal을 반환한다
- 핵심 routing 로직은 **pure function**으로 유지한다

dispatcher는 의심 많은 수문장입니다. planner requirement는 권위가 아니라 힌트입니다.

### 초기 구현 형태

초기 routing policy는 scoring registry가 아니라 **명시적 rule branch와 named
guard function**을 사용합니다.

이렇게 해야 runtime matrix가 작을 때 routing을 audit하기 쉽고 테스트하기
쉽습니다.

### Refusal semantics

fulfillable하지 않은 routing은 crash가 아니라 도메인 결과입니다.

따라서 routing은 다음 둘 중 하나를 반환합니다.

- `RoutingDecision`
- `RoutingRefusalReceipt`

예외는 programmer/configuration fault 같은 진짜 오류에만 사용합니다.

### Freshness boundary

routing inspection은 현재 snapshot/action state를 사용해야 하며, stale하거나
blocked된 lane에서 조용히 작업을 라우팅하면 안 됩니다.
dispatch와 intake 단계에서 이 freshness 경계는 더 강화됩니다.

## 결과

- planner는 runtime taxonomy를 알지 않아도 됨
- dispatcher가 실행 능력과 비용/안전 정책을 함께 통제할 수 있음
- founder/operator는 route가 왜 선택되었거나 거부되었는지 볼 수 있음
- 향후 execution plane 확장이 control plane contract를 오염시키지 않음
