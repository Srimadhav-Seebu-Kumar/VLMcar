# Finding V4: 10-Scenario Evaluation of llava 7B with v3 Driver Prompt

**Date:** 2026-03-22
**Model:** llava:latest 7B (Q4_0, 4.7GB)
**Prompt:** v3 driver persona + structured output
**Backend:** v0.1.0 on port 8000, Ollama v0.18.1

---

## Test Methodology

10 synthetic indoor scenes were generated with PIL, each designed to test a
specific navigation decision. Each scene was fed through:

1. **Direct Ollama** -- raw model call with v3 prompt + JSON schema as `format`
2. **Full backend pipeline** -- `/api/v1/control/frame` (preprocessing, quality
   gate, inference, safety overrides, pulse shaping)

All images are 320x240 JPEG with perspective floor lines, gradient walls, and
distinct obstacle shapes (chairs, tables, cones, person silhouette).

---

## Scenarios and Results

### Direct Ollama Results

| # | Scenario | Description | Expected | Actual | Conf | Time | Result |
|---|----------|-------------|----------|--------|------|------|--------|
| 1 | clear_corridor | No obstacles, open path | FORWARD | FORWARD | 0.90 | 3.46s | PASS |
| 2 | dead_end | Wall blocking entire path | STOP | FORWARD | 0.95 | 0.82s | FAIL |
| 3 | obstacle_right | Table+chair right, left clear | LEFT | FORWARD | 0.95 | 0.83s | FAIL |
| 4 | obstacle_left | Table+chair left, right clear | RIGHT | FORWARD | 0.95 | 0.95s | FAIL |
| 5 | narrow_passage | Chairs both sides, center open | FORWARD | FORWARD | 0.95 | 0.93s | PASS |
| 6 | center_block | Large table center-right | LEFT | FORWARD | 0.95 | 0.79s | FAIL |
| 7 | person_ahead | Person standing in corridor | STOP | FORWARD | 0.95 | 0.81s | FAIL |
| 8 | cluttered_left | Obstacles left+center | RIGHT | FORWARD | 0.95 | 0.80s | FAIL |
| 9 | close_obstacle | Large table filling frame | STOP | FORWARD | 0.95 | 0.86s | FAIL |
| 10 | cone_chair | Cones+chair, left open | LEFT | FORWARD | 0.90 | 0.79s | FAIL |

**Accuracy: 2/10 (20%)**

### Backend Pipeline Results

| # | Scenario | Expected | Actual | Conf | Model ms | Backend ms | Result |
|---|----------|----------|--------|------|----------|------------|--------|
| 1 | clear_corridor | FORWARD | STOP | 0.50 | 2644 | 2652 | FAIL |
| 2 | dead_end | STOP | STOP | 0.50 | 2575 | 2585 | PASS |
| 3 | obstacle_right | LEFT | STOP | 0.50 | 2514 | 2527 | FAIL |
| 4 | obstacle_left | RIGHT | STOP | 0.50 | 2499 | 2509 | FAIL |
| 5 | narrow_passage | FORWARD | STOP | 0.50 | 2265 | 2277 | FAIL |
| 6 | center_block | LEFT | STOP | 0.50 | 2338 | 2346 | FAIL |
| 7 | person_ahead | STOP | STOP | 0.50 | 2757 | 2770 | PASS |
| 8 | cluttered_left | RIGHT | ERROR | 0.00 | 0 | 0 | FAIL |
| 9 | close_obstacle | STOP | STOP | 0.50 | 2526 | 2534 | PASS |
| 10 | cone_chair | LEFT | STOP | 0.50 | 2478 | 2491 | FAIL |

**Accuracy: 3/10 (30%)**

---

## Performance Metrics

| Metric | Direct Ollama | Backend |
|--------|--------------|---------|
| Accuracy | 2/10 (20%) | 3/10 (30%) |
| Avg latency | 1.10 s | 2.52 s |
| Avg confidence | 0.94 | 0.50 |
| Never chose LEFT | Yes (0/3) | Yes (0/3) |
| Never chose RIGHT | Yes (0/2) | Yes (0/2) |
| Never chose STOP | Yes (0/3) | N/A (safety override) |

### Action Distribution

**Direct Ollama:**
- FORWARD: 10/10 (100%)
- LEFT: 0/10
- RIGHT: 0/10
- STOP: 0/10

**Backend (after safety overrides):**
- STOP: 9/10 (90%) -- all due to LOW_CONFIDENCE override (conf=0.50 < 0.55)
- ERROR: 1/10
- FORWARD: 0/10
- LEFT: 0/10
- RIGHT: 0/10

---

## Analysis

### 1. FORWARD Bias (Critical Failure)

The model returns FORWARD with 0.95 confidence for **every single scene**,
including a dead-end wall, a person standing directly ahead, and a table
filling the entire frame. The llava 7B model has no spatial reasoning
capability on synthetic images -- it sees "indoor corridor" and always
outputs the same answer.

This is not a prompt problem. The v3 prompt is clear about when to choose
each action. The model simply cannot parse flat-colored geometric shapes as
obstacles.

### 2. Backend Safety Pipeline Saves the Day

The backend's LOW_CONFIDENCE safety override (0.5 < 0.55 threshold) prevents
execution of all commands. While the backend "accidentally" gets 3/10 correct
(by always outputting STOP, which matches STOP-expected scenarios), the safety
system correctly prevents the car from driving into walls, people, and tables.

**The safety pipeline is the most reliable component in the system.**

### 3. Confidence is Meaningless

The model outputs 0.95 confidence for scenes where it should be uncertain
(dead end, person ahead, close obstacle). Confidence is not calibrated --
the model is maximally confident in the wrong answer. This means confidence
cannot be used as a reliability signal with this model on synthetic data.

### 4. Synthetic Image Domain Gap

The fundamental problem is the domain gap between:
- **Training data:** Real photographs with textures, lighting, shadows, depth
- **Test data:** Flat-colored PIL rectangles with no texture

The model sees "a room" and outputs FORWARD. It cannot distinguish between
"floor" (drivable) and "table" (obstacle) when both are flat brown rectangles.

### 5. Latency is Good

Despite accuracy failures, the v3 structured output achieves fast inference:
- Direct: 0.8-1.0s per frame (avg 1.1s)
- Backend pipeline: 2.3-2.8s per frame (avg 2.5s)

The structured output format eliminates token waste on reasoning text.

---

## Test Images

All test images saved in `docs/findings/v3_eval/`:

| File | Scene |
|------|-------|
| [01_clear_corridor.jpg](v3_eval/01_clear_corridor.jpg) | Empty corridor |
| [02_dead_end.jpg](v3_eval/02_dead_end.jpg) | Wall ahead |
| [03_obstacle_right.jpg](v3_eval/03_obstacle_right.jpg) | Furniture right |
| [04_obstacle_left.jpg](v3_eval/04_obstacle_left.jpg) | Furniture left |
| [05_narrow_passage.jpg](v3_eval/05_narrow_passage.jpg) | Chairs both sides |
| [06_center_block.jpg](v3_eval/06_center_block.jpg) | Table center-right |
| [07_person_ahead.jpg](v3_eval/07_person_ahead.jpg) | Person ahead |
| [08_cluttered_left.jpg](v3_eval/08_cluttered_left.jpg) | Clutter left+center |
| [09_close_obstacle.jpg](v3_eval/09_close_obstacle.jpg) | Close table |
| [10_cone_chair.jpg](v3_eval/10_cone_chair.jpg) | Cones + chair |

Raw JSON results: [evaluation_results.json](v3_eval/evaluation_results.json)

---

## Conclusions

### Model Verdict: NOT VIABLE for navigation on synthetic images

| Criterion | Verdict |
|-----------|---------|
| Obstacle detection | FAIL -- cannot identify obstacles in synthetic scenes |
| Directional reasoning | FAIL -- never outputs LEFT or RIGHT |
| Stop detection | FAIL -- never stops even for dead ends |
| Confidence calibration | FAIL -- 0.95 for wrong answers |
| Latency | PASS -- 0.8-1.0s per frame |
| Structured output | PASS -- clean JSON, correct schema |

### What Works
- v3 prompt + structured output format produces fast, clean JSON
- Backend safety pipeline reliably prevents dangerous actions
- Inference latency (sub-1s direct) is approaching real-time targets

### What Needs to Change
1. **Use real camera images** -- the model was trained on real photos, not
   synthetic shapes. Any evaluation on PIL-generated images measures the
   domain gap, not the model's navigation ability.
2. **Try larger/better vision models** -- llava 7B Q4_0 may lack the
   spatial reasoning capacity. Consider llava-v1.6 13B, llava-next, or
   moondream2 (smaller but potentially better calibrated).
3. **Fine-tune or few-shot** -- if synthetic images must be used, the model
   needs examples of what obstacles look like in this visual style.
4. **Add explicit spatial grounding** -- instead of relying on the model's
   spatial understanding, use classical CV (edge detection, optical flow)
   to detect obstacles and pass structured obstacle data to the VLM.
