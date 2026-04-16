.PHONY: env-init infra-up infra-down infra-logs venv install run compile

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
	. .venv/bin/activate && pip install -e .

run:
	. .venv/bin/activate && python -m v2_spring.cli --help

compile:
	python3 -m compileall src
