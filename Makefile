.PHONY: env-init env-local env-docker env-vm infra-up infra-down infra-logs venv install run compile test ci-smoke db-upgrade db-current db-history

COMPOSE_FILE=docker-compose.yml
ALEMBIC_BIN=$(if $(wildcard .venv/bin/alembic),.venv/bin/alembic,alembic)

env-init:
	@if [ -f .env ]; then \
		echo ".env already exists"; \
	else \
		cp .env.example .env && echo "Created .env from .env.example"; \
	fi

env-local:
	@if [ -f .env ] && [ "$${FORCE:-0}" != "1" ]; then \
		echo ".env already exists; rerun with FORCE=1 to overwrite"; \
	else \
		cp infra/env/local.env.example .env && echo "Created .env from infra/env/local.env.example"; \
	fi

env-docker:
	@if [ -f .env ] && [ "$${FORCE:-0}" != "1" ]; then \
		echo ".env already exists; rerun with FORCE=1 to overwrite"; \
	else \
		cp infra/env/docker.env.example .env && echo "Created .env from infra/env/docker.env.example"; \
	fi

env-vm:
	@if [ -f .env ] && [ "$${FORCE:-0}" != "1" ]; then \
		echo ".env already exists; rerun with FORCE=1 to overwrite"; \
	else \
		cp infra/env/vm.env.example .env && echo "Created .env from infra/env/vm.env.example"; \
	fi

infra-up:
	docker compose -f $(COMPOSE_FILE) up -d

infra-down:
	docker compose -f $(COMPOSE_FILE) down

infra-logs:
	docker compose -f $(COMPOSE_FILE) logs -f

venv:
	python3 -m venv .venv

install:
	. .venv/bin/activate && pip install -e '.[dev]'

run:
	. .venv/bin/activate && python -m v2_spring.cli --help

compile:
	python3 -m compileall src

test:
	PYTHONPATH=src pytest -q

db-upgrade:
	@DATABASE_URL=$${DATABASE_URL:-postgresql+psycopg://v2_spring:change_me_postgres@localhost:5432/v2_spring}; \
	$(ALEMBIC_BIN) upgrade head

db-current:
	@DATABASE_URL=$${DATABASE_URL:-postgresql+psycopg://v2_spring:change_me_postgres@localhost:5432/v2_spring}; \
	$(ALEMBIC_BIN) current

db-history:
	@DATABASE_URL=$${DATABASE_URL:-postgresql+psycopg://v2_spring:change_me_postgres@localhost:5432/v2_spring}; \
	$(ALEMBIC_BIN) history

ci-smoke:
	@DATABASE_URL=$${DATABASE_URL:-sqlite+pysqlite:///./.local/ci.db}; \
	mkdir -p .local; \
	RUN_ID=$$(DATABASE_URL="$$DATABASE_URL" v2-spring run create --project demo --goal "CI smoke run" --urgency normal --risk low | awk 'NR==1 {print $$3}'); \
	DATABASE_URL="$$DATABASE_URL" v2-spring run show "$$RUN_ID"
