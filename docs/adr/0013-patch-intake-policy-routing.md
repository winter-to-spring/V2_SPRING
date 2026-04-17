# ADR 0013: Patch Intake Policy Routing

## 상태

Accepted

## 배경

Step 12-c는 모든 worker-produced patch에 strict founder review gate를
도입했습니다. 첫 proof에서는 맞는 기본값이었지만, 명확한 처리량 병목도
드러났습니다.

- 저위험 단일 파일 patch도 고위험 patch와 같은 founder gate 뒤에서 기다린다
- execution-plane throughput이 founder attention에 묶인다
- intake model은 이미 risk와 eligibility를 알고 있지만, policy가 아직 이를
  활용하지 못한다

## 결정

명시적으로 저위험으로 분류된 patch intake에 대해 bounded auto-apply lane을
도입합니다.

정책은 의도적으로 좁습니다.

- low-risk patch intake만 후보가 된다
- 명시적으로 `auto_apply_eligible`인 intake만 이 lane을 사용할 수 있다
- auto-apply도 founder approval과 같은 strict patch apply + bounded validation을
  그대로 사용한다
- 그 외의 patch class는 모두 founder-review gated 상태를 유지한다

즉 auto-apply는 trust를 우회하는 것이 아니라, 더 좁은 risk class에 대해
같은 strict gate를 정책적으로 재사용하는 것입니다.

## 결과

### 긍정적

- 저위험 execution 결과가 항상 founder review 병목에 묶이지 않는다
- replay와 audit에 자동 적용 사실이 1급 기록으로 남는다
- founder attention을 medium/high-risk 변경에 집중할 수 있다

### 부정적

- intake policy가 더 stateful해지고, 테스트가 매우 중요해진다
- auto-apply lane 확장은 이후에도 명시적이고 좁게 유지해야 한다

## 후속

- broader trust/routing system은 여전히 defer한다
- review fatigue는 현재 bounded execution 범위에서는 해결되지만, 미래 모든
  worker class에 대해 자동으로 해결된 것은 아니다
