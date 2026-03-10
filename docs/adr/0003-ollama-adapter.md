# ADR 0003: Ollama Adapter Boundary

- Status: Accepted
- Date: 2026-03-10

## Context
Model providers and model IDs can change over project lifetime. Business logic must remain stable.

## Decision
Isolate model access behind an inference adapter interface with Ollama implementation as default.

## Consequences
- Pros: model swap without API/policy refactor, easier mocking in tests.
- Cons: adapter layer adds small abstraction overhead.
- Mitigation: keep adapter interface minimal and typed.
