# 환경 변수

V2_SPRING은 계속 진화 중이지만, 환경 변수 계약만큼은 로컬 개발, Docker
부트스트랩, VM 배포 사이에서 혼란 없이 유지될 만큼 안정적이어야 합니다.

## 프로필

`.env`의 시작점으로 아래 프로필 예시 중 하나를 사용합니다.

- 로컬 호스트 개발: [infra/env/local.env.example](/Users/changhyeon/Desktop/AI%20AGENT/infra/env/local.env.example)
- Docker 네트워크 내부 앱 프로세스: [infra/env/docker.env.example](/Users/changhyeon/Desktop/AI%20AGENT/infra/env/docker.env.example)
- VM / 단일 호스트 배포: [infra/env/vm.env.example](/Users/changhyeon/Desktop/AI%20AGENT/infra/env/vm.env.example)

도우미 타깃:

- `make env-local`
- `make env-docker`
- `make env-vm`

각 타깃은 선택한 프로필을 `.env`로 복사합니다. 이미 `.env`가 있으면
의도적으로 덮어쓰려는 경우에만 `FORCE=1`을 사용합니다.

## 소유 규칙

- `.env.example`은 루트 기본 로컬 예시입니다.
- `infra/env/*.env.example`은 배포 프로필 예시입니다.
- 시크릿은 커밋하지 않습니다. 예시는 비워 두거나 명백한 더미 값을 씁니다.
- `DATABASE_URL`은 애플리케이션 저장소를 가리키는 정식 변수입니다.
- `REDIS_URL`은 현재 일부 경로만 직접 쓰더라도 지금부터 예약하고 문서화합니다.

## 변수 계약

### 런타임

| 변수 | 필수 여부 | 예시 | 설명 |
| --- | --- | --- | --- |
| `APP_ENV` | yes | `local`, `container`, `production` | 배포 모드 라벨 |
| `TZ` | yes | `Asia/Seoul` | 인프라 컨테이너와 앱 로그가 공유하는 시간대 |
| `LOG_LEVEL` | yes | `info` | 런타임 로그 상세도 |

### 저장소 / 인프라

| 변수 | 필수 여부 | 예시 | 설명 |
| --- | --- | --- | --- |
| `POSTGRES_IMAGE` | local/docker | `postgres:17.9-bookworm` | Compose/bootstrap 이미지 고정값 |
| `POSTGRES_DB` | local/docker/vm | `v2_spring` | 기본 데이터베이스 이름 |
| `POSTGRES_USER` | local/docker/vm | `v2_spring` | 기본 데이터베이스 사용자 |
| `POSTGRES_PASSWORD` | local/docker/vm | `change_me_postgres` | 실제 배포에서는 반드시 교체 |
| `POSTGRES_PORT` | local/docker/vm | `5432` | 호스트 접근용 공개 포트 |
| `DATABASE_URL` | yes | `postgresql+psycopg://...` | 정식 SQLAlchemy URL. 가능하면 `psycopg` 드라이버 사용 |
| `REDIS_IMAGE` | local/docker | `redis:8.6` | Compose/bootstrap 이미지 고정값 |
| `REDIS_PORT` | local/docker/vm | `6379` | 호스트 접근용 공개 포트 |
| `REDIS_URL` | yes | `redis://localhost:6379/0` | 조정/캐시 URL |

### Planner / 모델 어댑터

| 변수 | 필수 여부 | 예시 | 설명 |
| --- | --- | --- | --- |
| `PLANNER_PROVIDER` | yes | `scripted`, `openai`, `anthropic` | 기본값은 `scripted` |
| `PLANNER_OPENAI_MODEL` | optional | `gpt-4o` | provider가 OpenAI일 때 사용 |
| `PLANNER_ANTHROPIC_MODEL` | optional | `claude-3-5-sonnet-latest` | provider가 Anthropic일 때 사용 |
| `PLANNER_TIMEOUT_SECONDS` | yes | `30` | transport timeout |
| `PLANNER_MAX_RETRIES` | yes | `2` | 재시도 가능한 transport 오류에 대한 최대 재시도 횟수 |
| `PLANNER_MAX_CONTEXT_CHARS` | yes | `12000` | 프롬프트 컨텍스트 상한 |
| `OPENAI_API_KEY` | provider-specific | 예시에서는 비움 | OpenAI transport 사용 시에만 필요 |
| `ANTHROPIC_API_KEY` | provider-specific | 예시에서는 비움 | Anthropic transport 사용 시에만 필요 |

### 향후 실행 어댑터용 선택 변수

| 변수 | 필수 여부 | 예시 | 설명 |
| --- | --- | --- | --- |
| `GITHUB_TOKEN` | optional | 예시에서는 비움 | 향후 GitHub 연동 실행 lane 예약 변수 |
| `NOTION_TOKEN` | optional | 예시에서는 비움 | 향후 Notion 연동 실행 lane 예약 변수 |

## 호스트 이름 관례

### 로컬 호스트 프로세스

- `DATABASE_URL=postgresql+psycopg://...@localhost:5432/...`
- `REDIS_URL=redis://localhost:6379/0`

### Docker 네트워크 내부에서 실행되는 앱

- `DATABASE_URL=postgresql+psycopg://...@postgres:5432/...`
- `REDIS_URL=redis://redis:6379/0`

### VM / 단일 호스트 배포

- Postgres/Redis가 같은 머신에 있으면 보통 `127.0.0.1`
- private host나 managed-service hostname은 의도적으로 그런 배포를
  선택했을 때만 사용

## 배포 노트

- Step 21 이후 PostgreSQL은 migration-controlled 저장소로 취급해야
  합니다. 배포 환경에서 ORM의 암묵적 bootstrap에 기대지 마세요.
- 올바른 `.env` 프로필을 적용한 뒤 `make db-upgrade` 또는 Alembic
  명령을 우선 사용하세요.
- `v2-spring doctor`는 앱이 올바른 dialect와 migration 상태를 보고
  있는지 가장 빠르게 확인하는 방법입니다.
