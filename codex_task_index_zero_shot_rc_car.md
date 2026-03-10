
# Codex Task Index - Zero-Shot RC Car Repo

## Foundations
- T01 Bootstrap the monorepo
- T02 Write architecture and ADR documents
- T03 Define shared schemas and contracts
- T04 Add developer tooling and environment checks

## Backend Core
- T05 Build the FastAPI application skeleton
- T06 Implement session lifecycle endpoints
- T07 Implement frame ingestion endpoint
- T08 Implement storage layer with SQLite
- T09 Add frame storage and preprocessing
- T10 Add quality gate and early-stop logic
- T11 Implement Ollama inference adapter
- T12 Build prompt manager and structured-output parser
- T13 Implement decision policy, safety overrides, and pulse shaping
- T14 Wire the full backend control pipeline
- T15 Add telemetry, heartbeat, and error reporting routes
- T16 Add a minimal operator dashboard and manual override

## Testing Without Hardware
- T17 Build a simulated edge client
- T18 Build replay and evaluation tooling
- T19 Add backend smoke tests and benchmark scripts

## Firmware
- T20 Scaffold the firmware project
- T21 Implement motor driver and pulse execution module
- T22 Implement camera capture module
- T23 Implement Wi-Fi and HTTP client modules
- T24 Implement firmware state machine and control loop
- T25 Add firmware failsafes and diagnostics

## Full Integration
- T26 Add a backend mock for firmware-first testing
- T27 Run real end-to-end integration with backend pipeline
- T28 Add optional sensor extension points (IR/GPS stubs)
- T29 Add calibration and tuning tools

## Quality, CI, and Research Readiness
- T30 Add complete test coverage across layers
- T31 Add CI workflows
- T32 Complete deployment and demo documentation
- T33 Add final acceptance scripts and demo mode
- T34 Add research output utilities
- T35 Final repo polish and consistency pass
