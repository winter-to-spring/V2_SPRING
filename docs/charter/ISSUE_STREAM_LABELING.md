# 이슈 스트림 라벨링

## 목적

V2_SPRING은 이제 진행 상황을 두 종류로 나눠 봐야 할 만큼 커졌습니다.

- engine readiness
- product readiness

이 구분이 없으면 이슈 목록과 마일스톤 리뷰가 왜곡됩니다. 컨트롤 플레인은
거의 끝났는데, 사용자 표면은 아직 초기일 수 있기 때문입니다.

## 규칙

모든 새 GitHub 이슈는 정확히 하나의 스트림 태그로 시작해야 합니다.

- `[engine]`
- `[product]`

이 태그는 필수입니다.

## 의미

### `[engine]`

작업이 주로 시스템 substrate를 바꾸는 경우 `[engine]`을 사용합니다.

- control plane
- planner / governance
- runtime / workers
- storage / Postgres / Redis
- lease / concurrency / reconciliation
- deployment foundations
- observability / reliability / operational hardening

### `[product]`

작업이 주로 사용자 또는 운영자 표면을 바꾸는 경우 `[product]`를 사용합니다.

- user GUI
- operator dashboard
- founder workflow surfaces
- GitHub / GitLab / external product integrations
- demo flows
- onboarding and UX

## 제목 형식

이슈 제목은 다음 순서를 사용합니다.

`[stream] [execution-prefix] Step N - Title`

예시:

- `[engine] [코어] Step 23 - Postgres churn reduction + audit retention`
- `[product] [UI] Step P1 - Founder/operator dashboard shell`
- `[engine] [인프라] Step 24 - Compose deployment baseline`

## 혼합 작업

하나의 작업 조각에 engine과 product 작업이 함께 있으면:

1. 가능하면 두 이슈로 나눕니다
2. 나누기 어렵다면 주된 스트림 하나를 고릅니다
3. 대응되는 이슈를 링크하거나 본문에 부수 영향을 명시합니다

큰 혼합 이슈 하나보다, 작은 명확한 이슈 둘이 더 낫습니다.

## 진행률 보고

이제부터 진행률은 두 트랙으로 읽습니다.

- engine readiness
- product readiness

전체 서비스 준비도는 계속 이야기할 수 있지만, 이 두 트랙을 대신하면 안
됩니다.

## 왜 중요한가

이 규칙은 로드맵 논의를 정직하게 유지합니다.

엔진만 거의 끝난 상태를 두고 "이제 거의 끝났다"고 말하는 실수를 막고,
실배포 전까지 남은 제품 작업량을 과소평가하지 않게 해줍니다.
