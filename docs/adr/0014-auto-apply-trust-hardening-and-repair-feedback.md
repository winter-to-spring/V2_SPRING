# ADR 0014: Auto-Apply Trust Hardening과 Repair Feedback

## 상태

Accepted

## 배경

Step 15는 low-risk patch intake 결과에 대해 bounded auto-apply lane을 열었습니다.
덕분에 명백히 안전한 변경은 founder 병목을 줄일 수 있었지만, 동시에 새로운
trust 공백도 드러났습니다.

- 의미상 중앙 파일이 여전히 auto-apply 가능해 보일 수 있다
- planner가 하나의 위험한 변경을 여러 trivial patch로 쪼개는 방식으로 우회할 수 있다
- 단순 키워드 스캔은 obfuscated dangerous pattern을 놓칠 수 있다
- 상세한 validation feedback은 repair 품질을 높이지만, bounded한 wasteful retry
  loop도 함께 만들 수 있다

## 결정

bounded auto-apply lane을 replay-visible한 명시적 규칙으로 강화합니다.

정책은 이제 아래를 포함합니다.

- single-file / low-line-count patch라도 central/protected file이면 founder
  review를 강제하는 규칙
- 같은 파일이나 모듈에 대해 bounded window 안에서 반복되는 auto-apply를 감지하는
  burst detection
- hard block finding과 soft warning finding을 분리하는 lightweight structural
  scan
- strict apply / validation receipt로부터 만들어진 detailed patch repair feedback
- repair 시도가 계속 수렴하지 않을 때 founder guidance로 escalation하는 bounded
  repair retry quota

첫 구현은 score-based가 아니라 explicit하고 deterministic한 방식으로 유지합니다.

## 결과

### 긍정적

- auto-apply lane이 좁고 믿을 만한 범위에 머문다
- replay와 founder surface가 왜 auto-apply가 막혔는지 또는 reroute되었는지
  설명할 수 있다
- 실패한 auto-apply가 planner에 더 유의미한 repair context를 제공한다
- 반복 repair failure가 조용한 background retry로 숨지 않는다

### 부정적

- patch policy logic이 더 stateful해지고, 강한 테스트가 계속 필요하다
- static central-file rule은 여전히 일부 shadow centrality를 모델링하지 못한다
- structural scan은 의도적으로 lightweight하고 보수적이다

## 후속

- static protected-file rule을 넘어서는 richer centrality는 defer한다
- 더 강한 semantic analysis도 defer한다
- trust 확장은 implicit하지 않고 explicit하고 bounded한 방식으로만 열어야 한다
