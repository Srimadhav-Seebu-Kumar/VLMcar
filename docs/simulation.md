# Simulation and Real-World Camera Loop

## Purpose
This workflow validates the full backend control contract without ESP32 hardware first, then runs the same backend loop with a laptop camera in a real environment.

All paths are local/offline:
- simulator frames are generated locally
- backend runs locally
- Ollama runs locally
- STOP is the fallback on any backend/client uncertainty

## Prerequisites
1. Python environment is installed and dependencies are available:
   - `make install`
2. Local Ollama is running and model is available:
   - `ollama serve`
   - `ollama pull llava`
3. Backend environment variables are configured:
   - copy `.env.example` to `.env`
   - adjust `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, and quality/pulse settings if needed

## Start backend
```bash
make run-backend
```

Check health:
```bash
make smoke-backend
```

## Run deterministic mock backend (optional)
If you want deterministic command validation first:
```bash
python simulator/mock_backend.py --scenario alternating_turns --port 8010
python -m simulator.cli episode --frame-url http://127.0.0.1:8010/api/v1/control/frame --map straight_corridor
```

## Run full simulator episode against real backend + Ollama
```bash
python -m simulator.cli episode --map straight_corridor --max-steps 40
```

Outputs:
- `tmp_artifacts/sim_runs/<session_id>/frames/*.jpg`
- `tmp_artifacts/sim_runs/<session_id>/topdown/*.png` (unless disabled)
- `tmp_artifacts/sim_runs/<session_id>/steps.jsonl`
- `tmp_artifacts/sim_runs/<session_id>/summary.json`

Each step record includes `trace_id`, `session_id`, command fields, and state transitions.

## Replay recorded frames against backend
```bash
python -m simulator.cli replay --steps-jsonl tmp_artifacts/sim_runs/<session_id>/steps.jsonl
```

Replay output:
- `tmp_artifacts/sim_runs/replay_results.jsonl` (or custom `--output-jsonl`)

This is useful for prompt/model regression checks with fixed frame data.

## Real environment loop using laptop camera
Run the same control contract with webcam frames:
```bash
python -m simulator.cli webcam --camera-index 0 --max-frames 200 --show-preview
```

Behavior:
- captures webcam frame
- JPEG-encodes frame
- posts to `/api/v1/control/frame`
- prints returned action/reason/trace metadata
- stops automatically on backend `STOP` by default
- press `q` to exit preview window manually

## Suggested real-environment safety flow
1. Keep RC car powered off.
2. Run webcam loop while pointing laptop camera at the driving scene.
3. Confirm returned actions and reason codes are plausible.
4. If model confidence/parse quality is unstable, keep STOP-only mode until tuned.

## Environment variables
Useful simulator/webcam env vars:
- `SIM_BACKEND_FRAME_URL`
- `SIM_DEVICE_ID`
- `SIM_MAP_NAME`
- `SIM_OUTPUT_DIR`
- `SIM_MAX_STEPS`
- `SIM_FRAME_WIDTH`
- `SIM_FRAME_HEIGHT`
- `SIM_JPEG_QUALITY`
- `SIM_CAMERA_INDEX`
- `SIM_CAMERA_WIDTH`
- `SIM_CAMERA_HEIGHT`
- `SIM_CAMERA_MAX_FRAMES`
- `SIM_CAMERA_PREVIEW`
- `SIM_STOP_ON_BACKEND_STOP`
