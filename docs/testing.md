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

## Definition of done for touched behavior
- behavior implemented with explicit error handling
- tests added for normal and failure paths
- docs updated
- config updated if new variables are introduced
