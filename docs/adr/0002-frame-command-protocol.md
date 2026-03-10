# ADR 0002: Frame-Command Protocol

- Status: Accepted
- Date: 2026-03-10

## Context
Firmware and backend must interoperate reliably under intermittent connectivity and model uncertainty.

## Decision
Use strict contract-driven HTTP communication:
- multipart frame upload with typed metadata
- JSON command response with explicit enum action and bounded actuation values

## Consequences
- Pros: deterministic integration, easier test simulation, explicit validation failures.
- Cons: protocol versioning overhead.
- Mitigation: keep canonical JSON schemas in `contracts/` and mirror in Pydantic models.
