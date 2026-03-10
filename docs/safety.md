# Safety Model

## Safety assumptions
- Model output is probabilistic and can be wrong.
- Network and backend outages are expected conditions.
- Low-cost camera input may be noisy or low quality.

## Safety rules
- Fallback action is always `STOP`.
- Firmware starts in stationary mode.
- Commands are short pulses and expire.
- Any timeout or parse error forces immediate STOP.
- Emergency stop endpoint and firmware ESTOP block motion.

## Backend safety controls
- Request validation on all fields.
- Image quality gates can reject uncertain frames (too dark/bright/blurry/low quality).
- Parser requires strict structured output.
- Decision policy enforces low-confidence STOP overrides.
- Decision policy clamps PWM and duration bounds.
- Inference failures produce explicit STOP response with reason code.

## Firmware safety controls
- Watchdog timer and backend timeout handling.
- Motor auto-stop at end of pulse.
- No queued motion commands.
- Overlapping command execution denied.

## Operational safety checklist
1. Confirm ESTOP endpoint is reachable.
2. Confirm backend and model health checks pass.
3. Confirm firmware logs show state machine healthy.
4. Perform first runs at low PWM and short pulses.
5. Keep manual physical cutoff accessible during demos.
