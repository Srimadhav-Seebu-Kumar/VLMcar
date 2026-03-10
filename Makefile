SHELL := /bin/bash

.PHONY: install lint format typecheck test run-backend check-env smoke-backend smoke-ollama firmware-build precommit

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
