# ADR 0004: Safety-First Motion Pulses

- Status: Accepted
- Date: 2026-03-10

## Context
Local VLM inference may have variable latency and occasional malformed outputs. Continuous drive commands are high risk.

## Decision
Use pulse-based actuation only:
- each command has finite `duration_ms`
- firmware auto-stops after pulse
- any error path falls back to STOP

## Consequences
- Pros: lower runaway risk, easier to reason about control loop, clearer safety boundaries.
- Cons: lower top speed and stop-and-go motion.
- Mitigation: tune pulse duration and PWM with calibration tools.
