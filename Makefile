.PHONY: env-init infra-up infra-down infra-logs venv install run compile test ci-smoke db-upgrade db-current db-history

COMPOSE_FILE=docker-compose.yml

env-init:
	@if [ -f .env ]; then \
		echo ".env already exists"; \
	else \
		cp .env.example .env && echo "Created .env from .env.example"; \
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
	@DATABASE_URL=$${DATABASE_URL:-postgresql://v2_spring:change_me_postgres@localhost:5432/v2_spring}; \
	alembic upgrade head

db-current:
	@DATABASE_URL=$${DATABASE_URL:-postgresql://v2_spring:change_me_postgres@localhost:5432/v2_spring}; \
	alembic current

db-history:
	@DATABASE_URL=$${DATABASE_URL:-postgresql://v2_spring:change_me_postgres@localhost:5432/v2_spring}; \
	alembic history

ci-smoke:
	@DATABASE_URL=$${DATABASE_URL:-sqlite+pysqlite:///./.local/ci.db}; \
	mkdir -p .local; \
	RUN_ID=$$(DATABASE_URL="$$DATABASE_URL" v2-spring run create --project demo --goal "CI smoke run" --urgency normal --risk low | awk 'NR==1 {print $$3}'); \
	DATABASE_URL="$$DATABASE_URL" v2-spring run show "$$RUN_ID"
