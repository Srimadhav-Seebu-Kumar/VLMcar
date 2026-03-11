SHELL := /bin/bash
STEPS_JSONL ?= tmp_artifacts/sim_runs/steps.jsonl

.PHONY: install lint format typecheck test run-backend run-sim run-webcam replay-sim check-env smoke-backend smoke-ollama firmware-build precommit

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check .

format:
	python -m ruff format .

typecheck:
	python -m mypy backend tools simulator

test:
	python -m pytest

run-backend:
	python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

run-sim:
	python -m simulator.cli episode

replay-sim:
	python -m simulator.cli replay --steps-jsonl $(STEPS_JSONL)

run-webcam:
	python -m simulator.cli webcam --show-preview

check-env:
	python tools/check_env.py

smoke-backend:
	python tools/smoke_test_backend.py

smoke-ollama:
	python tools/smoke_test_ollama.py

firmware-build:
	pio run -d firmware

precommit:
	python -m pre_commit run --all-files
