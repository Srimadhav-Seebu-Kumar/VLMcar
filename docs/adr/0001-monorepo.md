# ADR 0001: Monorepo Strategy

- Status: Accepted
- Date: 2026-03-10

## Context
The project contains tightly-coupled backend, firmware, contracts, simulator, and documentation. Separate repositories would increase integration drift risk.

## Decision
Use a single monorepo containing all project layers.

## Consequences
- Pros: one source of truth for contracts, easier coordinated changes, simpler onboarding.
- Cons: larger repository and mixed-language tooling.
- Mitigation: explicit folder boundaries and task-specific commands.
