# Testing Strategy

## Test layers
- Unit tests: schemas, parsers, policy, utility functions.
- Integration tests: API routes with TestClient and storage.
- End-to-end simulation: mock edge client against local backend.
- Firmware host checks: parser and state logic where hardware-free.

## Mandatory safety tests
- Invalid command values fail validation.
- Parser failures produce STOP command.
- Timeout paths return STOP.
- Low confidence and malformed outputs are blocked.

## Test commands
- `make test`: run Python test suite.
- `make smoke-backend`: verify backend endpoint health.
- `make smoke-ollama`: verify local Ollama availability.
- `make firmware-build`: compile firmware sources.

## Hardware-free workflow
1. Run backend locally.
2. Run simulator against control endpoint.
3. Review logs for action distribution and stop rate.
4. Use replay tooling to compare prompt versions.

## Mock backend for firmware bring-up
Use deterministic scenarios when firmware integration starts before model tuning is stable:

```bash
python simulator/mock_backend.py --scenario always_stop --port 8010
python simulator/mock_backend.py --scenario always_forward --port 8010
python simulator/mock_backend.py --scenario alternating_turns --port 8010
python simulator/mock_backend.py --scenario timeout --timeout-seconds 3 --port 8010
```

## Full local integration path
1. Start backend pipeline: `python -m uvicorn backend.app.main:app --reload`.
2. Validate backend health: `python tools/smoke_test_backend.py`.
3. Build firmware: `python -m platformio run -d firmware -e esp32cam`.
4. Set firmware backend URL in `firmware/include/config.h`.
5. Flash firmware and monitor serial logs for `trace_id` and `session_id`.
6. Verify command fields (`action`, PWM, `duration_ms`, `safe_to_execute`) are present and parsed.

## Definition of done for touched behavior
- behavior implemented with explicit error handling
- tests added for normal and failure paths
- docs updated
- config updated if new variables are introduced
