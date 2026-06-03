PYTHON = /Users/himanshusharma/venv/bin/python3
UVICORN = /Users/himanshusharma/venv/bin/uvicorn
RUFF = $(PYTHON) -m ruff

.PHONY: help api seed web compose-up compose-down check lint format docker-build clean

help:
	@echo "Available targets:"
	@echo "  api          - Run the FastAPI backend with hot-reload"
	@echo "  seed         - Seed database with demo data"
	@echo "  web          - Run the React frontend in dev mode"
	@echo "  compose-up   - Start all local services via docker compose"
	@echo "  compose-down - Stop all local services"
	@echo "  check        - Compile check, seed, and run verification suite"
	@echo "  lint         - Run ruff lint check on python code"
	@echo "  format       - Run ruff formatter on python code"
	@echo "  docker-build - Build the web-api Docker image locally"
	@echo "  clean        - Remove temporary files, build artifacts, cache, and db"

api:
	$(UVICORN) platformops.main:app --app-dir apps/api --reload

seed:
	$(PYTHON) scripts/seed_demo.py

web:
	cd apps/web && npm run dev

compose-up:
	docker compose -f ops/compose/docker-compose.local.yml up -d

compose-down:
	docker compose -f ops/compose/docker-compose.local.yml down

check:
	$(PYTHON) -m py_compile $$(find apps/api scripts ops/docker -name '*.py')
	$(PYTHON) scripts/seed_demo.py
	$(PYTHON) scripts/verify_platformops.py

lint:
	$(RUFF) check apps/api scripts

format:
	$(RUFF) format apps/api scripts

docker-build:
	docker build -f ops/docker/web-api/Dockerfile -t platformops-api:latest .

clean:
	rm -rf data/platformops.db data/runtime/*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
