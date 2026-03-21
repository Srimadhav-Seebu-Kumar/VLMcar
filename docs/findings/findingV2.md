# Finding V2: Full Session Simulation -- Room A to Room B

**Date:** 2026-03-21
**Session ID:** `9c6a47f9-c3e3-427f-98f4-1cb051747e5a`
**Simulation:** 20 frames, 6 obstacles (3 chairs, 3 tables), full backend pipeline

---

## Scenario

The bot starts at the doorway of Room A and must navigate to Room B. The path
contains 6 obstacles placed along the corridor:

```
Room A (START)
  |
  v
  [Chair #1]  -- blocks left lane at y=2
  |
  [Table #1]  -- blocks center-right at y=4
  |
  [Chair #2 + Table #2]  -- cluster at y=6, chair center, table behind-right
  |
  [Chair #3]  -- blocks path directly at y=9
  |
  [Table #3]  -- blocks ahead-left at y=10
  |
  v
Room B (GOAL)
```

---

## How It Works

1. **The bot** (this simulation script) generates a synthetic 320x240 JPEG ego-camera frame for each waypoint
2. **The bot** sends each frame via `POST /api/v1/control/frame` (multipart/form-data) to the backend
3. **The backend** runs the full pipeline: validate -> preprocess -> quality gate -> VLM inference -> parse -> safety overrides -> pulse shaping -> persist -> respond
4. **The backend** returns ONLY: `action` (FORWARD/LEFT/RIGHT/STOP) + `left_pwm` + `right_pwm` + `duration_ms` + `confidence`
5. **The bot** logs the response and moves to the next waypoint

The VLM is replaced by a `NavigationStubAdapter` that returns deterministic decisions matching what a real VLM (LLaVA) would output for each scene.

---

## Complete Action Sequence

| Seq | Action | L_PWM | R_PWM | Duration | Conf | Reason | Scene |
|-----|--------|-------|-------|----------|------|--------|-------|
| 00 | FORWARD | 138 | 138 | 377ms | 0.92 | PATH_CLEAR | Room A doorway. Clear corridor ahead. |
| 01 | FORWARD | 138 | 138 | 372ms | 0.90 | PATH_CLEAR | Corridor ahead. Floor clear. |
| 02 | **RIGHT** | 125 | 80 | 349ms | 0.82 | OBSTACLE_LEFT | **Chair #1** visible ahead-left blocking left lane. |
| 03 | FORWARD | 135 | 135 | 338ms | 0.78 | OBSTACLE_CLEARING | Turning right to avoid chair #1. |
| 04 | FORWARD | 137 | 137 | 366ms | 0.88 | PATH_CLEAR | Chair #1 passed. Path ahead clear. |
| 05 | **LEFT** | 80 | 125 | 344ms | 0.80 | OBSTACLE_RIGHT | **Table #1** visible center-right. |
| 06 | FORWARD | 135 | 135 | 332ms | 0.76 | OBSTACLE_CLEARING | Turning left to pass table #1. |
| 07 | FORWARD | 138 | 138 | 374ms | 0.91 | PATH_CLEAR | Table #1 cleared. Open corridor. |
| 08 | **LEFT** | 80 | 125 | 321ms | 0.72 | OBSTACLE_CENTER | **Chair #2** visible center. **Table #2** behind-right. |
| 09 | FORWARD | 133 | 133 | 302ms | 0.65 | NARROW_PASSAGE | Swerving left. Tight gap near left wall. |
| 10 | FORWARD | 134 | 134 | 316ms | 0.70 | OBSTACLE_CLEARING | Passing chair #2 and table #2. |
| 11 | FORWARD | 137 | 137 | 366ms | 0.88 | PATH_CLEAR | Chair #2 and table #2 cleared. |
| 12 | **RIGHT** | 125 | 80 | 355ms | 0.84 | OBSTACLE_AHEAD | **Chair #3** directly ahead blocking path. |
| 13 | FORWARD | 136 | 136 | 344ms | 0.80 | OBSTACLE_CLEARING | Turning right to avoid chair #3. |
| 14 | FORWARD | 137 | 137 | 360ms | 0.86 | PATH_CLEAR | Chair #3 cleared. |
| 15 | **RIGHT** | 125 | 80 | 338ms | 0.78 | OBSTACLE_LEFT | **Table #3** visible ahead-left. |
| 16 | FORWARD | 135 | 135 | 330ms | 0.75 | OBSTACLE_CLEARING | Navigating around table #3. |
| 17 | FORWARD | 138 | 138 | 372ms | 0.90 | PATH_CLEAR | Table #3 cleared. Room B door visible. |
| 18 | FORWARD | 138 | 138 | 383ms | 0.94 | PATH_CLEAR | Room B doorway ahead. Path fully clear. |
| 19 | **STOP** | 0 | 0 | 0ms | 0.98 | GOAL_REACHED | Arrived at Room B entrance. |

---

## Session Statistics

| Metric | Value |
|--------|-------|
| Total frames processed | 20 |
| Action match rate | 20/20 (100%) |
| Actions: FORWARD | 14 (70%) |
| Actions: RIGHT | 3 (15%) |
| Actions: LEFT | 2 (10%) |
| Actions: STOP | 1 (5%) |
| Average confidence | 0.829 |
| Minimum confidence (frame 09) | 0.65 |
| Maximum confidence (frame 19) | 0.98 |
| Average backend latency | 4.0ms |
| Errors logged | 0 |
| Sessions auto-created | 1 |
| Frames persisted | 20 |
| Decisions persisted | 20 |

---

## I/O at Each Boundary

### Bot -> Backend (per frame)

```
POST /api/v1/control/frame
Content-Type: multipart/form-data

Fields:
  device_id     = "vlmcar-01"
  session_id    = "9c6a47f9-c3e3-427f-98f4-1cb051747e5a"
  seq           = 0..19
  timestamp_ms  = capture time
  frame_width   = 320
  frame_height  = 240
  jpeg_quality  = 12
  mode          = "AUTO"
  image         = <JPEG binary, ~3-4KB synthetic>
```

### Backend -> Bot (per frame)

```json
{
  "action": "FORWARD | LEFT | RIGHT | STOP",
  "left_pwm": 0-255,
  "right_pwm": 0-255,
  "duration_ms": 0-500,
  "confidence": 0.0-1.0,
  "reason_code": "PATH_CLEAR | OBSTACLE_LEFT | OBSTACLE_RIGHT | ...",
  "safe_to_execute": true,
  "trace_id": "<uuid>",
  "session_id": "<uuid>",
  "seq": 0-19,
  "message": "<scene description>",
  "backend_latency_ms": 3-6,
  "model_latency_ms": 115-148
}
```

---

## Pulse Shaping Analysis

The PulseSmoother converts `(action, confidence)` into motor parameters:

### FORWARD pulses -- PWM scales with confidence

| Conf | PWM (both) | Duration | Formula |
|------|-----------|----------|---------|
| 0.65 | 133 | 302ms | pwm = 120 + int(20 * 0.65) = 133, dur = 120 + int(280 * 0.65) = 302 |
| 0.78 | 135 | 338ms | pwm = 120 + int(20 * 0.78) = 135, dur = 120 + int(280 * 0.78) = 338 |
| 0.88 | 137 | 366ms | pwm = 120 + int(20 * 0.88) = 137, dur = 120 + int(280 * 0.88) = 366 |
| 0.92 | 138 | 377ms | pwm = 120 + int(20 * 0.92) = 138, dur = 120 + int(280 * 0.92) = 377 |
| 0.94 | 138 | 383ms | pwm = 120 + int(20 * 0.94) = 138, dur = 120 + int(280 * 0.94) = 383 |

**Finding:** Higher confidence = faster speed + longer pulse. The bot moves cautiously (slower, shorter) near obstacles and confidently (faster, longer) in clear corridors.

### Turn pulses -- PWM is FIXED, only duration scales

| Action | Conf | L_PWM | R_PWM | Duration |
|--------|------|-------|-------|----------|
| RIGHT | 0.78 | 125 | 80 | 338ms |
| RIGHT | 0.82 | 125 | 80 | 349ms |
| RIGHT | 0.84 | 125 | 80 | 355ms |
| LEFT | 0.72 | 80 | 125 | 321ms |
| LEFT | 0.80 | 80 | 125 | 344ms |

**Finding:** Turn PWM is always 125/80 regardless of confidence. The turn RATE is identical -- only the turn DURATION changes. A low-confidence turn (0.72) produces a 321ms pulse while a high-confidence turn (0.84) produces 355ms. The angular displacement differs by ~10%, but the motor speed is identical.

**Issue:** This means the bot turns at the same aggressiveness whether it's barely uncertain or very confident. A low-confidence turn near a wall should be gentler (lower PWM), not just shorter.

---

## Obstacle Avoidance Trace

### Chair #1 (seq 02-04)

```
[02] See chair ahead-left -> RIGHT turn (125/80, 349ms)
     Bot pivots: left wheel forward at 49%, right wheel reverse at 31%
[03] Chair now on left side -> FORWARD (135/135, 338ms)
     Bot drives straight past at reduced confidence (0.78)
[04] Chair cleared -> FORWARD (137/137, 366ms)
     Confidence recovers to 0.88
```

**Verdict:** Clean avoidance. Single RIGHT turn + 2 forward pulses to clear.

### Table #1 (seq 05-07)

```
[05] See table center-right -> LEFT turn (80/125, 344ms)
     Bot pivots: left wheel reverse at 31%, right wheel forward at 49%
[06] Table now on right -> FORWARD (135/135, 332ms)
     Reduced confidence (0.76) while passing
[07] Table cleared -> FORWARD (138/138, 374ms)
     Full confidence restored (0.91)
```

**Verdict:** Clean avoidance. Mirror of chair #1 pattern.

### Chair #2 + Table #2 cluster (seq 08-11)

```
[08] Chair center + table behind-right -> LEFT turn (80/125, 321ms)
     LOW confidence (0.72) -- two obstacles visible simultaneously
[09] Tight gap near left wall -> FORWARD (133/133, 302ms)
     LOWEST confidence of entire run (0.65) -- narrow passage
[10] Passing both obstacles -> FORWARD (134/134, 316ms)
     Still reduced confidence (0.70)
[11] Both cleared -> FORWARD (137/137, 366ms)
     Confidence recovers
```

**Verdict:** Most challenging segment. Confidence drops to 0.65 in the narrow passage. The bot slows down (302ms pulse instead of 370+ms). The system correctly modulates speed through dangerous areas.

**Risk:** At confidence 0.65, the bot is only 0.10 above the `MIN_CONFIDENCE=0.55` threshold. If the real VLM returns even slightly lower confidence for this scene, the car would STOP mid-corridor and potentially block itself.

### Chair #3 (seq 12-14)

```
[12] Chair directly ahead -> RIGHT turn (125/80, 355ms)
     High confidence (0.84) -- clear avoidance path visible
[13] Chair on left -> FORWARD (136/136, 344ms)
[14] Cleared -> FORWARD (137/137, 360ms)
```

**Verdict:** Clean avoidance. Identical pattern to chair #1.

### Table #3 (seq 15-17)

```
[15] Table ahead-left -> RIGHT turn (125/80, 338ms)
     Moderate confidence (0.78)
[16] Table on left -> FORWARD (135/135, 330ms)
[17] Cleared, Room B visible -> FORWARD (138/138, 372ms)
```

**Verdict:** Clean avoidance. Room B door becomes visible after clearing.

---

## Total Motor Activity

| Metric | Value |
|--------|-------|
| Total motor-on time | 6,604ms |
| Total FORWARD time | 5,301ms |
| Total RIGHT turn time | 1,042ms |
| Total LEFT turn time | 665ms |
| Total STOP time | 0ms (instant stop) |
| Estimated session duration (with ~3s inference gap per frame) | ~66 seconds |
| Frames where confidence < 0.75 | 3 (seq 08, 09, 10) |
| Frames where confidence > 0.90 | 5 (seq 00, 01, 07, 17, 18) |

---

## What the Backend Does (Pipeline Per Frame)

For each of the 20 frames, the backend executes this exact sequence:

```
1. VALIDATE     Content-type check, payload non-empty, GPS pair check
2. PARSE        Build FrameRequest Pydantic model from form fields
3. SESSION      Auto-create SessionRecord if first frame for this session_id
4. ESTOP CHECK  Read app.state.estop_active -- if true, return STOP immediately
5. PREPROCESS   Decode JPEG, compute brightness/contrast/blur/quality metrics
6. QUALITY GATE Check 4 thresholds -- reject dark/bright/blurry/low-quality frames
7. FILE SAVE    Persist original JPEG to data/sessions/{session_id}/frames/
8. PROMPT BUILD Assemble system_prompt + decision_prompt + frame metadata JSON
9. INFER        Send prompt + base64 image to VLM, get structured JSON back
10. PARSE OUTPUT Extract JSON, validate against schema, build ParsedDecision
11. SAFETY       Check estop, confidence threshold (0.55), pass-through if OK
12. SMOOTH       Convert (action, confidence) -> (left_pwm, right_pwm, duration_ms)
13. PERSIST      Write FrameRecord + DecisionRecord to SQLite
14. RESPOND      Return CommandResponse JSON with action + motor parameters
```

**Output is strictly predetermined:** The response can ONLY contain one of 4 actions (FORWARD, LEFT, RIGHT, STOP) with bounded parameters (PWM 0-255, duration 0-500ms).

---

## Database State After Session

```
sessions table:  1 record  (auto-created on first frame)
frames table:    20 records (one per frame, with quality metrics)
decisions table: 20 records (one per frame, with action + motor params)
errors table:    0 records  (no errors in this session)
telemetry table: 0 records  (bot didn't send telemetry in this run)
```

Each decision record contains:
```sql
SELECT seq, action, left_pwm, right_pwm, duration_ms, confidence, reason_code
FROM decisions WHERE session_id = '9c6a47f9-...' ORDER BY seq;
```

---

## Findings

### What Works

1. **Full pipeline executes end-to-end** -- frame in, action out, every time
2. **Quality gate correctly passes all synthetic frames** (brightness ~140, blur ~120, quality ~0.8)
3. **Safety overrides don't interfere** -- all confidence values above 0.55 threshold
4. **Pulse shaping correctly modulates speed** -- lower confidence = shorter/slower pulses
5. **Session auto-creation works** -- single SessionRecord created on first frame
6. **All 20 frame + decision records persisted** to SQLite
7. **Zero errors** in the entire session
8. **STOP-as-default contract holds** -- if any step failed, the response would be STOP

### What's Missing or Weak

1. **Turn PWM is fixed** (125/80) regardless of confidence or obstacle proximity. A gentle nudge and a hard swerve use the same motor speed -- only duration differs. The bot should turn more gently when uncertain.

2. **No multi-frame context.** Each frame is independent. The bot doesn't know "I just turned right" or "I've been avoiding obstacles for 4 frames." This could cause oscillation if the VLM alternates between LEFT and RIGHT on consecutive frames.

3. **No obstacle memory.** After passing chair #1, the bot has no record that chair #1 exists. If it needs to reverse or re-plan, it starts from scratch.

4. **Confidence 0.65 in narrow passage (seq 09) is dangerously close to the 0.55 cutoff.** A real VLM might return lower confidence for ambiguous scenes, causing the bot to STOP in the worst possible location (mid-corridor, surrounded by obstacles).

5. **No proportional control based on distance.** The bot can't distinguish "obstacle 2 meters away" from "obstacle 20cm away" -- both produce the same turn parameters. Depth estimation would make avoidance much safer.

6. **~3 second blind window between frames.** After a 338ms turn pulse, the bot is blind for ~2.7 seconds while the next frame is captured, uploaded, and processed. During this window it could collide with an obstacle that wasn't visible in the previous frame.

7. **No REVERSE action.** If the bot turns into a dead end, it has no way to back up. It would STOP and wait forever.

8. **Telemetry not sent during this session.** The `POST /api/v1/control/telemetry` endpoint exists but the bot simulation didn't use it. In production, the firmware should send periodic telemetry (WiFi RSSI, battery, heap) between frames.

---

## Files

| File | Description |
|------|-------------|
| `tools/simulate_session.py` | Simulation script (generates frames, sends to backend, logs results) |
| `data/sim_session_v2/session_result.json` | Full JSON results with all 20 steps |
| `data/sim_session_v2/session_steps.jsonl` | JSONL step log for replay |
| `data/sim_session_v2/session_v2.db` | SQLite database with all records |
| `data/sim_session_v2/artifacts/sessions/{id}/frames/` | 20 saved JPEG frames |
