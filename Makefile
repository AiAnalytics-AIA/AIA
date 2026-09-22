# AIA developer entry points. Every target is safe to run repeatedly.
.DEFAULT_GOAL := help
SHELL := /bin/bash
VENV := .venv

# Use the project venv when it exists, otherwise whatever python is on PATH.
# CI installs into the runner's interpreter and has no .venv, so hardcoding the
# venv path breaks every target that uses it -- which is how `make openapi`
# failed on the first push.
PY := $(shell [ -x $(VENV)/bin/python ] && echo $(VENV)/bin/python || command -v python3)
PIP := $(PY) -m pip
BIN := $(shell [ -d $(VENV)/bin ] && echo $(VENV)/bin/ || echo "")

.PHONY: help setup deps services migrate migration dev dev-api dev-web \
        test test-core test-api test-parity test-web lint format typecheck \
        check openapi clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: deps ## One-time setup: Python venv, dependencies, web packages
	@cd apps/web && npm install
	@test -f .env || cp .env.example .env
	@echo "Setup complete. Next: make services && make migrate && make dev"

deps: ## Create the venv and install Python packages in editable mode
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install -q --upgrade pip
	@$(PIP) install -q -e "packages/aia_core[dev,postgres]"
	@$(PIP) install -q -e "apps/api[dev]"

services: ## Start Postgres and MinIO, and wait until healthy
	@docker compose up -d --wait

migrate: ## Apply database migrations
	@$(PY) -m alembic upgrade head

migration: ## Create a migration from model changes: make migration m="add jobs"
	@test -n "$(m)" || (echo 'Usage: make migration m="description"' && exit 1)
	@$(PY) -m alembic revision --autogenerate -m "$(m)"

dev: ## Run the API and web client together
	@trap 'kill 0' EXIT; $(MAKE) dev-api & $(MAKE) dev-web & wait

dev-api: ## Run the API with autoreload on :8000
	@$(BIN)uvicorn aia_api.main:app --reload --port 8000

dev-web: ## Run the web client on :3000
	@cd apps/web && npm run dev

test: test-core test-api ## Run all Python tests

test-core: ## Domain and repository tests
	@$(PY) -m pytest packages/aia_core -q

test-api: ## API tests
	@$(PY) -m pytest apps/api -q

test-parity: ## Compare against the legacy prototype (needs AIA_LEGACY_REFERENCE)
	@$(PY) -m pytest packages/aia_core -q -m parity

test-web: ## Web client tests
	@cd apps/web && npm test --if-present

lint: ## Lint Python and the web client
	@$(BIN)ruff check packages/aia_core apps/api migrations
	@$(BIN)ruff format --check packages/aia_core apps/api migrations
	@cd apps/web && npm run lint

format: ## Auto-format Python and the web client
	@$(BIN)ruff format packages/aia_core apps/api migrations
	@$(BIN)ruff check --fix packages/aia_core apps/api migrations

typecheck: ## Type-check Python and the web client
	@$(BIN)mypy packages/aia_core/src apps/api/src
	@cd apps/web && npx tsc --noEmit

check: lint typecheck test ## Everything CI runs

openapi: ## Write the OpenAPI document to openapi.json
	@$(PY) -c "import json; from aia_api.main import create_app; \
	  from aia_api.config import Settings, Environment; \
	  print(json.dumps(create_app(Settings(env=Environment.LOCAL)).openapi(), indent=2))" \
	  > openapi.json
	@echo "wrote openapi.json"

clean: ## Remove caches and build artifacts
	@find . -type d -name __pycache__ -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache .mypy_cache
