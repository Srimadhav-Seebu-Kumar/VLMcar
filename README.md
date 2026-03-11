# Zero-Shot RC Car Monorepo

Safety-first, offline-first software stack for zero-shot navigation of an ESP32-CAM RC car using a local vision-language model (Ollama) and a local Python backend.

## Project goals
- Keep runtime fully local and offline.
- Drive using short motion pulses with STOP as the default fallback.
- Preserve strict backend-firmware contracts with typed schemas.
- Support hardware-free validation through simulator and replay tooling.
- Keep research logs and metadata for reproducible experiments.

## Repository layout
- `backend/`: FastAPI backend, schemas, control pipeline, tests.
- `firmware/`: PlatformIO ESP32-CAM firmware source.
- `contracts/`: JSON schemas for backend-firmware communication.
- `simulator/`: Edge-client simulation and replay tools.
- `tools/`: Environment checks, smoke tests, and utilities.
- `prompts/`: Versioned local model prompts and decision schemas.
- `docs/`: Architecture, API, firmware, safety, testing, and ADRs.
- `notebooks/`: Optional analysis notebooks.
- `.github/workflows/`: CI workflow definitions.

## Quick start
1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies:
   ```bash
   make install
   ```
3. Copy `.env.example` to `.env` and set local values.
4. Validate local environment:
   ```bash
   make check-env
   ```
5. Run static checks and tests:
   ```bash
   make lint
   make typecheck
   make test
   ```

## Common commands
- `make run-backend`: Run backend service locally.
- `make smoke-backend`: Validate backend health endpoint.
- `make smoke-ollama`: Validate local Ollama endpoint.
- `make firmware-build`: Build PlatformIO firmware project.
- `python -m simulator.cli episode`: Run simulator episode against backend.
- `python -m simulator.cli replay --steps-jsonl <path>`: Replay stored frames.
- `python -m simulator.cli webcam --show-preview`: Run laptop camera control loop.

## Simulation and laptop camera
- Full simulation workflow: [`docs/simulation.md`](docs/simulation.md)
- Testing strategy and hardware-free validation: [`docs/testing.md`](docs/testing.md)

## Safety defaults
- Any uncertainty, parsing error, timeout, or invalid input must result in `STOP`.
- Motion commands are pulse-based and expire automatically.
- Manual emergency stop is required before real hardware tests.
