# Environment Variables

V2_SPRING is still evolving, but the environment contract should already be
stable enough that local development, Docker-based bootstrap, and VM-style
deployment do not drift in confusing ways.

## Profiles

Use one of these profile examples as the starting point for `.env`.

- local host development: [infra/env/local.env.example](/Users/changhyeon/Desktop/AI%20AGENT/infra/env/local.env.example)
- Docker-networked app process: [infra/env/docker.env.example](/Users/changhyeon/Desktop/AI%20AGENT/infra/env/docker.env.example)
- VM / single-host deployment: [infra/env/vm.env.example](/Users/changhyeon/Desktop/AI%20AGENT/infra/env/vm.env.example)

Helper targets:

- `make env-local`
- `make env-docker`
- `make env-vm`

Each target copies the chosen profile to `.env`. If `.env` already exists, use
`FORCE=1` to overwrite it deliberately.

## Ownership rules

- `.env.example` is the root local default.
- `infra/env/*.env.example` are deployment-profile examples.
- secrets should not be committed; examples stay blank or use obvious dummy values.
- `DATABASE_URL` is the canonical application storage variable.
- `REDIS_URL` is reserved and documented now even if only part of the system
  currently consumes it directly.

## Variable contract

### Runtime

| Variable | Required | Example | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | yes | `local`, `container`, `production` | Deployment mode label. |
| `TZ` | yes | `Asia/Seoul` | Shared timezone for infra containers and app logs. |
| `LOG_LEVEL` | yes | `info` | Runtime log verbosity contract. |

### Storage / infrastructure

| Variable | Required | Example | Notes |
| --- | --- | --- | --- |
| `POSTGRES_IMAGE` | local/docker | `postgres:17.9-bookworm` | Compose/bootstrap image pin. |
| `POSTGRES_DB` | local/docker/vm | `v2_spring` | Default database name. |
| `POSTGRES_USER` | local/docker/vm | `v2_spring` | Default database user. |
| `POSTGRES_PASSWORD` | local/docker/vm | `change_me_postgres` | Replace in real deployments. |
| `POSTGRES_PORT` | local/docker/vm | `5432` | Published port for host access. |
| `DATABASE_URL` | yes | `postgresql+psycopg://...` | Canonical SQLAlchemy URL. Prefer `psycopg` driver form. |
| `REDIS_IMAGE` | local/docker | `redis:8.6` | Compose/bootstrap image pin. |
| `REDIS_PORT` | local/docker/vm | `6379` | Published port for host access. |
| `REDIS_URL` | yes | `redis://localhost:6379/0` | Coordination/cache URL. |

### Planner / model adapter

| Variable | Required | Example | Notes |
| --- | --- | --- | --- |
| `PLANNER_PROVIDER` | yes | `scripted`, `openai`, `anthropic` | Defaults to `scripted`. |
| `PLANNER_OPENAI_MODEL` | optional | `gpt-4o` | Used when provider is OpenAI. |
| `PLANNER_ANTHROPIC_MODEL` | optional | `claude-3-5-sonnet-latest` | Used when provider is Anthropic. |
| `PLANNER_TIMEOUT_SECONDS` | yes | `30` | Transport timeout. |
| `PLANNER_MAX_RETRIES` | yes | `2` | Retry count for retryable transport errors. |
| `PLANNER_MAX_CONTEXT_CHARS` | yes | `12000` | Prompt context bound. |
| `OPENAI_API_KEY` | provider-specific | blank in examples | Required only when using OpenAI transport. |
| `ANTHROPIC_API_KEY` | provider-specific | blank in examples | Required only when using Anthropic transport. |

### Optional future execution adapters

| Variable | Required | Example | Notes |
| --- | --- | --- | --- |
| `GITHUB_TOKEN` | optional | blank in examples | Reserved for future GitHub-integrated execution lanes. |
| `NOTION_TOKEN` | optional | blank in examples | Reserved for future Notion-integrated execution lanes. |

## Hostname conventions

### Local host process

- `DATABASE_URL=postgresql+psycopg://...@localhost:5432/...`
- `REDIS_URL=redis://localhost:6379/0`

### App running inside Docker network

- `DATABASE_URL=postgresql+psycopg://...@postgres:5432/...`
- `REDIS_URL=redis://redis:6379/0`

### VM / single-host deployment

- usually `127.0.0.1` if Postgres/Redis live on the same machine
- use a private host or managed-service hostname only when that is an explicit deployment choice

## Deployment notes

- For Step 21 and beyond, PostgreSQL should be treated as migration-controlled.
  Do not rely on implicit ORM bootstrap in deployment environments.
- Prefer `make db-upgrade` or direct Alembic commands after the right `.env`
  profile is in place.
- `v2-spring doctor` is the quickest way to confirm the app sees the right
  dialect and migration state.
