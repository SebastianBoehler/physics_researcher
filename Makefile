UV ?= uv
COMPOSE ?= docker compose

.PHONY: sync lint format typecheck test up down api worker worker-lammps test-lammps seed-demo

sync:
	$(UV) sync --all-packages

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy .

test:
	$(UV) run pytest

up:
	$(UV) run autolab up

down:
	$(UV) run autolab down

api:
	$(UV) run uvicorn autolab.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	$(UV) run python -m autolab.worker.main

worker-lammps:
	$(COMPOSE) --profile lammps up worker-lammps

test-lammps:
	$(COMPOSE) --profile lammps run --rm --no-deps worker-lammps uv run pytest tests/integration/test_real_simulator_execution.py -k lammps

seed-demo:
	$(UV) run autolab seed-demo
