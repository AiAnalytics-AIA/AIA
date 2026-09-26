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

.PHONY: help setup deps services migrate migration dev dev-api dev-web dev-worker \
        test test-core test-api test-worker test-executors test-parity test-golden test-oracle parity-status test-web web_design ui-workbench ui-workbench-status ui-workbench-down ui-capture ui-fixtures ui-research \
        lint format typecheck \
        layer_check exposure_check check verify openapi clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: deps ## One-time setup: Python venv, dependencies, web packages
	@cd apps/web && npm install
	@test -f .env || cp .env.example .env
	@echo "Setup complete. Next: make services && make migrate && make dev"

deps: ## Create the venv and install Python packages in editable mode
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(VENV)/bin/python -m pip install -q --upgrade pip
	@$(VENV)/bin/python -m pip install -q -e "packages/aia_core[dev,postgres,s3,report,bedrock]"
	@$(VENV)/bin/python -m pip install -q -e "apps/worker[dev]"
	@$(VENV)/bin/python -m pip install -q -e "apps/executors[dev]"
	@$(VENV)/bin/python -m pip install -q -e "apps/api[dev]"

services: ## Start Postgres and MinIO, and wait until healthy
	@docker compose up -d --wait

migrate: ## Apply database migrations
	@if [ -n "$$DATABASE_URL" ] || [ ! -f .env ]; then \
	  $(PY) -m alembic upgrade head; \
	else \
	  set -a; . ./.env; set +a; $(PY) -m alembic upgrade head; \
	fi

migration: ## Create a migration from model changes: make migration m="add jobs"
	@test -n "$(m)" || (echo 'Usage: make migration m="description"' && exit 1)
	@$(PY) -m alembic revision --autogenerate -m "$(m)"

dev: ## Run the API and web client together
	@trap 'kill 0' EXIT; $(MAKE) dev-api & $(MAKE) dev-web & wait

dev-api: ## Run the API with autoreload on :8000
	@$(BIN)uvicorn aia_api.main:app --reload --port 8000

dev-worker: ## Run one worker with the real executors (needs DATABASE_URL and AIA_STORAGE_*)
	@AIA_WORKER_EXECUTORS=$${AIA_WORKER_EXECUTORS:-aia_executors.registry:build_registry} \
	  $(PY) -m aia_worker

seed-develop: ## Provision the idempotent synthetic develop world (needs DATABASE_URL, AIA_SEED_OWNER_EMAIL)
	@$(PY) -m aia_executors.seed

dev-web: ## Run the web client on :3000
	@cd apps/web && npm run dev

test: test-core test-api test-worker test-executors ## Run all Python tests

test-core: ## Domain and repository tests
	@$(PY) -m pytest packages/aia_core -q

test-api: ## API tests
	@$(PY) -m pytest apps/api -q

test-worker: ## Worker tests (the multi-process suite needs a PostgreSQL DATABASE_URL)
	@$(PY) -m pytest apps/worker -q

test-executors: ## Step executor, seed and smoke-module tests
	@$(PY) -m pytest apps/executors -q

test-parity: ## Compare against the legacy prototype (needs AIA_LEGACY_REFERENCE)
	@$(PY) -m pytest packages/aia_core -q -m parity

test-golden: ## Golden-fixture gates (needs the reference repo: sibling clone or AIA_REFERENCE_REPO)
	@$(PY) -m pytest packages/aia_core/tests/test_golden_fixtures.py -q -rs

test-oracle: ## Differential tests against the running 18.6.6 unit (needs AIA_LEGACY_REFERENCE_URL + credentials)
	@$(PY) -m pytest packages/aia_core -q -m oracle -rs

parity-status: ## Parity verdict per capability, from a fresh run of every suite
	@mkdir -p tmp/junit
	-@$(PY) -m pytest packages/aia_core -q -o junit_family=xunit1 --junit-xml=tmp/junit/core.xml
	-@$(PY) -m pytest apps/api -q -o junit_family=xunit1 --junit-xml=tmp/junit/api.xml
	@$(PY) tools/parity_status.py --junit tmp/junit/core.xml tmp/junit/api.xml \
	  --markdown tmp/parity-status.md --json tmp/parity-status.json
	@echo "full report: tmp/parity-status.md"

test-web: ## Web client tests
	@cd apps/web && npm test --if-present

ui-workbench: ## AIA's client-first interface + the classic 18.6.6 one on this machine (fictional panel): 127.0.0.1:8780
	@AIA_API_PYTHON=$${AIA_API_PYTHON:-$(PY)} python3 tools/ui_workbench/workbench.py up

ui-workbench-status: ## Is the UI workbench running, and is the skin applied?
	@python3 tools/ui_workbench/workbench.py status

ui-capture: ## Screenshot every screen of the workbench, bare and skinned -> tmp/ui-workbench/shots/<time>/index.html
	@node tools/ui_workbench/capture.mjs

ui-fixtures: ## Write the workbench's fictional research projects (the screens that show an AI answer)
	@python3 tools/ui_workbench/fixture_project.py

ui-research: ## One research run end to end in a browser on the workbench: Run -> Progress -> Results (fictional fieldwork)
	@node tools/ui_workbench/research_journey.mjs

ui-workbench-down: ## Stop the UI workbench
	@python3 tools/ui_workbench/workbench.py down

web_design: ## Design tokens and the 18.6.6 skin: generated files current, contrast / palette / accent evidence holds
	@cd apps/web && npm run tokens:check && npm run skin:check && npm run check:design

lint: ## Lint Python and the web client
	@$(BIN)ruff check packages/aia_core apps/api apps/worker apps/executors migrations
	@$(BIN)ruff format --check packages/aia_core apps/api apps/worker apps/executors migrations
	@cd apps/web && npm run lint

format: ## Auto-format Python and the web client
	@$(BIN)ruff format packages/aia_core apps/api apps/worker apps/executors migrations
	@$(BIN)ruff check --fix packages/aia_core apps/api apps/worker apps/executors migrations

typecheck: ## Type-check Python and the web client
	@$(BIN)mypy packages/aia_core/src apps/api/src apps/worker/src apps/executors/src
	@cd apps/web && npx tsc --noEmit

layer_check: ## Enforce the layering rules in ARCHITECTURE.md
	@./tools/layer_check.sh

exposure_check: ## Fail if detailed reference material reached this repository
	@./tools/exposure_check.sh

check: lint typecheck layer_check exposure_check web_design test test-web ## Everything CI runs

verify: ## The pre-commit sequence from CLAUDE.md §10, in order
	@$(MAKE) typecheck
	@$(MAKE) layer_check
	@$(MAKE) exposure_check
	@$(BIN)ruff format --check packages/aia_core apps/api apps/worker apps/executors migrations
	@$(MAKE) test
	@$(MAKE) web_design
	@$(MAKE) test-web

openapi: ## Write the OpenAPI document to openapi.json
	@$(PY) -c "import json; from aia_api.main import create_app; \
	  from aia_api.config import Settings, Environment; \
	  print(json.dumps(create_app(Settings(env=Environment.LOCAL)).openapi(), indent=2))" \
	  > openapi.json
	@echo "wrote openapi.json"

clean: ## Remove caches and build artifacts
	@find . -type d -name __pycache__ -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache .mypy_cache
