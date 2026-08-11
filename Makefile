PYTHON ?= python3
UVICORN ?= uvicorn
RUFF ?= $(PYTHON) -m ruff
PYTEST ?= $(PYTHON) -m pytest

PLATFORMOPS_ISOLATED_COMPOSE ?= ops/compose/docker-compose.isolated.yml
PLATFORMOPS_ISOLATED_PROJECT ?= platformops-isolated
PLATFORMOPS_ISOLATED_IMAGE ?= platformops:isolated

# Optional services are never enabled implicitly.  Set one or both variables
# to 1 when explicitly testing Mailpit or the GlitchTip-compatible endpoint.
ISOLATED_MAILPIT_PROFILE = $(if $(filter 1 true yes,$(PLATFORMOPS_ENABLE_MAILPIT)),--profile mailpit,)
ISOLATED_GLITCHTIP_PROFILE = $(if $(filter 1 true yes,$(PLATFORMOPS_ENABLE_GLITCHTIP)),--profile glitchtip,)

.PHONY: help api seed web compose-up compose-down check compile unit build docker-build \
	isolated-verify isolated-up isolated-down lint format clean

help:
	@echo "Available targets:"
	@echo "  api              - Run the FastAPI backend with hot-reload"
	@echo "  seed             - Explicitly seed the selected local database (mutating)"
	@echo "  web              - Run the React frontend in dev mode"
	@echo "  compose-up/down  - Legacy local stack controls (9002; preserve live use)"
	@echo "  compile          - Compile Python sources without running the application"
	@echo "  unit             - Run shipped unit tests"
	@echo "  build            - Build the combined frontend/API production image"
	@echo "  isolated-verify  - Validate isolated Compose/Dockerfile/E2E safety statically"
	@echo "  isolated-up      - Start only the project-scoped isolated stack"
	@echo "  isolated-down    - Stop isolated services and retain project volumes"
	@echo "  check            - Run non-mutating compile, unit, and isolated checks"
	@echo "  lint             - Run ruff lint check on Python code"
	@echo "  format           - Run ruff formatter on Python code"
	@echo "  clean            - Remove temporary files/build artifacts/cache (mutating)"

api:
	$(UVICORN) platformops.main:app --app-dir apps/api --reload

# Seeding is intentionally a separate, explicitly requested target.  No
# verification/check target invokes it and no isolated target drops a DB.
seed:
	$(PYTHON) scripts/seed_demo.py

web:
	cd apps/web && npm run dev

# Existing local controls are kept for the live-compatible stack.  New
# verification should use isolated-up/isolated-down below.
compose-up:
	docker compose -f ops/compose/docker-compose.local.yml up -d

compose-down:
	docker compose -f ops/compose/docker-compose.local.yml down

compile:
	$(PYTHON) -m compileall -q apps/api scripts ops

unit:
	$(PYTEST) -q apps/api/tests

build:
	docker build -f ops/docker/web-api/Dockerfile -t $(PLATFORMOPS_ISOLATED_IMAGE) .

docker-build: build

isolated-verify:
	$(PYTHON) scripts/verify_isolated_runtime.py

isolated-up: isolated-verify
	docker compose --project-name $(PLATFORMOPS_ISOLATED_PROJECT) --file $(PLATFORMOPS_ISOLATED_COMPOSE) \
		--profile isolated $(ISOLATED_MAILPIT_PROFILE) $(ISOLATED_GLITCHTIP_PROFILE) up -d

# Deliberately omit --volumes: this target stops the isolated project while
# retaining its project-scoped data.  Remove volumes only as a separately
# reviewed, explicit Docker Compose command.
isolated-down:
	docker compose --project-name $(PLATFORMOPS_ISOLATED_PROJECT) --file $(PLATFORMOPS_ISOLATED_COMPOSE) \
		--profile isolated --profile mailpit --profile glitchtip down

check: compile unit isolated-verify

lint:
	$(RUFF) check apps/api scripts

format:
	$(RUFF) format apps/api scripts

clean:
	rm -rf data/platformops.db data/runtime/*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
