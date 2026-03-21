"""Simulate a full navigation session: Room A -> Room B, avoiding 3 chairs and 3 tables.

This script acts AS the bot. It generates synthetic ego-camera frames for a
scripted path through a room with 6 obstacles, sends each frame through the
full backend pipeline (preprocess -> quality gate -> infer -> safety -> smoother ->
persist), and logs the complete action sequence.

The VLM is replaced by a NavigationStubAdapter that returns deterministic
decisions based on the frame sequence number, simulating what a real VLM
would see at each point on the path.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.app.core.config import AppSettings
from backend.app.main import create_app
from backend.app.services.inference import InferenceRequest, InferenceResult
from backend.app.services.storage import clear_cached_db_handles, session_scope
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Scene definition: 25 waypoints from Room A door to Room B door
# ---------------------------------------------------------------------------

@dataclass
class Waypoint:
    """A single point on the navigation path with scene context."""
    seq: int
    x: float          # grid x position (0-10)
    y: float          # grid y position (0-12)
    heading: float     # degrees, 0=north, 90=east
    scene: str         # what the camera sees
    hazards: list[str]
    expected_action: str
    expected_confidence: float
    expected_reason: str


WAYPOINTS: list[Waypoint] = [
    # --- Room A: starting position ---
    Waypoint(0,  2, 0, 0,   "Room A doorway. Clear corridor ahead. Hardwood floor.",
             [], "FORWARD", 0.92, "PATH_CLEAR"),
    Waypoint(1,  2, 1, 0,   "Corridor ahead. Floor clear. Walls on both sides.",
             [], "FORWARD", 0.90, "PATH_CLEAR"),
    Waypoint(2,  2, 2, 0,   "Chair #1 visible ahead-left blocking left lane.",
             ["chair ahead-left"], "RIGHT", 0.82, "OBSTACLE_LEFT"),
    Waypoint(3,  3, 2, 45,  "Turning right to avoid chair #1. Chair now on left side.",
             ["chair left-side"], "FORWARD", 0.78, "OBSTACLE_CLEARING"),
    Waypoint(4,  4, 3, 0,   "Chair #1 passed. Path ahead clear. Straightening.",
             [], "FORWARD", 0.88, "PATH_CLEAR"),

    # --- Entering corridor with table #1 ---
    Waypoint(5,  4, 4, 0,   "Table #1 visible center-right. Large rectangular obstacle.",
             ["table center-right"], "LEFT", 0.80, "OBSTACLE_RIGHT"),
    Waypoint(6,  3, 4, 315, "Turning left to pass table #1. Table now on right.",
             ["table right-side"], "FORWARD", 0.76, "OBSTACLE_CLEARING"),
    Waypoint(7,  2, 5, 0,   "Table #1 cleared. Open corridor segment.",
             [], "FORWARD", 0.91, "PATH_CLEAR"),

    # --- Chair #2 and Table #2 cluster ---
    Waypoint(8,  2, 6, 0,   "Chair #2 visible ahead center. Table #2 behind it on right.",
             ["chair center", "table behind-right"], "LEFT", 0.72, "OBSTACLE_CENTER"),
    Waypoint(9,  1, 6, 315, "Swerving left around chair #2. Tight gap near left wall.",
             ["chair right", "wall close-left"], "FORWARD", 0.65, "NARROW_PASSAGE"),
    Waypoint(10, 1, 7, 0,   "Passing chair #2 and table #2. Obstacles on right.",
             ["chair right", "table right"], "FORWARD", 0.70, "OBSTACLE_CLEARING"),
    Waypoint(11, 1, 8, 0,   "Chair #2 and table #2 cleared. Path opens up.",
             [], "FORWARD", 0.88, "PATH_CLEAR"),

    # --- Chair #3 blocks path ---
    Waypoint(12, 1, 9, 0,   "Chair #3 directly ahead blocking path. Must go right.",
             ["chair directly-ahead"], "RIGHT", 0.84, "OBSTACLE_AHEAD"),
    Waypoint(13, 2, 9, 45,  "Turning right to avoid chair #3. Chair on left now.",
             ["chair left"], "FORWARD", 0.80, "OBSTACLE_CLEARING"),
    Waypoint(14, 3, 9, 0,   "Chair #3 cleared. Approaching Table #3.",
             [], "FORWARD", 0.86, "PATH_CLEAR"),

    # --- Table #3: final obstacle ---
    Waypoint(15, 3, 10, 0,  "Table #3 visible ahead-left. Large dining table.",
             ["table ahead-left"], "RIGHT", 0.78, "OBSTACLE_LEFT"),
    Waypoint(16, 4, 10, 45, "Navigating around table #3. Table on left.",
             ["table left-side"], "FORWARD", 0.75, "OBSTACLE_CLEARING"),
    Waypoint(17, 5, 11, 0,  "Table #3 almost cleared. Room B door visible ahead.",
             ["table behind-left"], "FORWARD", 0.90, "PATH_CLEAR"),

    # --- Final approach to Room B ---
    Waypoint(18, 5, 11.5, 0, "Room B doorway ahead. Path fully clear.",
             [], "FORWARD", 0.94, "PATH_CLEAR"),
    Waypoint(19, 5, 12, 0,  "Arrived at Room B entrance. Goal reached.",
             [], "STOP", 0.98, "GOAL_REACHED"),
]


# ---------------------------------------------------------------------------
# Navigation-aware stub VLM adapter
# ---------------------------------------------------------------------------

class NavigationStubAdapter:
    """Simulates a VLM by returning scripted decisions based on frame sequence."""

    def __init__(self, waypoints: list[Waypoint]) -> None:
        self._waypoints = {w.seq: w for w in waypoints}

    async def infer(self, request: InferenceRequest) -> InferenceResult:
        # Extract seq from the prompt metadata
        seq = self._extract_seq(request.prompt)
        wp = self._waypoints.get(seq, self._default_waypoint(seq))

        decision = json.dumps({
            "action": wp.expected_action,
            "confidence": wp.expected_confidence,
            "reason_code": wp.expected_reason,
            "scene_summary": wp.scene,
            "hazards": wp.hazards,
        })

        return InferenceResult(
            raw_output=decision,
            model_latency_ms=int(50 + wp.expected_confidence * 100),
            provider_payload={"provider": "navigation-stub", "seq": seq},
        )

    def _extract_seq(self, prompt: str) -> int:
        try:
            import re
            match = re.search(r'"seq"\s*:\s*(\d+)', prompt)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return -1

    def _default_waypoint(self, seq: int) -> Waypoint:
        return Waypoint(seq, 0, 0, 0, "Unknown position.", [], "STOP", 0.50, "UNKNOWN")


# ---------------------------------------------------------------------------
# Frame generator: creates synthetic ego-camera JPEG for each waypoint
# ---------------------------------------------------------------------------

def generate_frame(wp: Waypoint) -> bytes:
    """Generate a 320x240 synthetic ego-camera frame for the waypoint."""

    img = Image.new("RGB", (320, 240))
    draw = ImageDraw.Draw(img)

    # Floor (brown hardwood)
    draw.rectangle([0, 120, 320, 240], fill=(160, 120, 80))
    # Ceiling
    draw.rectangle([0, 0, 320, 50], fill=(210, 210, 210))
    # Left wall
    draw.rectangle([0, 0, 30, 240], fill=(140, 140, 140))
    # Right wall
    draw.rectangle([290, 0, 320, 240], fill=(140, 140, 140))
    # Far wall / corridor
    draw.rectangle([30, 50, 290, 120], fill=(190, 190, 180))

    # Draw obstacles based on hazards
    for hazard in wp.hazards:
        h = hazard.lower()
        if "chair" in h:
            color = (100, 60, 30)  # dark brown chair
            if "left" in h:
                draw.rectangle([40, 130, 110, 200], fill=color)
                draw.rectangle([50, 100, 100, 135], fill=(90, 50, 25))  # chair back
            elif "right" in h:
                draw.rectangle([210, 130, 280, 200], fill=color)
                draw.rectangle([220, 100, 270, 135], fill=(90, 50, 25))
            elif "center" in h or "ahead" in h:
                draw.rectangle([120, 110, 200, 190], fill=color)
                draw.rectangle([130, 80, 190, 115], fill=(90, 50, 25))
        elif "table" in h:
            color = (80, 50, 20)  # darker brown table
            if "left" in h:
                draw.rectangle([30, 120, 140, 180], fill=color)
                # Table legs
                draw.rectangle([35, 175, 45, 210], fill=(60, 35, 15))
                draw.rectangle([125, 175, 135, 210], fill=(60, 35, 15))
            elif "right" in h:
                draw.rectangle([180, 120, 290, 180], fill=color)
                draw.rectangle([185, 175, 195, 210], fill=(60, 35, 15))
                draw.rectangle([275, 175, 285, 210], fill=(60, 35, 15))
            elif "center" in h:
                draw.rectangle([100, 110, 220, 170], fill=color)
        elif "wall" in h and "close" in h:
            if "left" in h:
                draw.rectangle([0, 0, 50, 240], fill=(130, 130, 130))

    # Draw Room B doorway on final frames
    if wp.seq >= 18:
        draw.rectangle([100, 50, 220, 120], fill=(40, 40, 40))  # dark doorway
        draw.rectangle([100, 48, 220, 55], fill=(120, 80, 40))  # door frame

    # Add horizon line
    draw.line([30, 120, 290, 120], fill=(170, 170, 160), width=1)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------

@dataclass
class StepLog:
    seq: int
    timestamp_ms: int
    scene: str
    hazards: list[str]
    expected_action: str
    actual_action: str
    action_match: bool
    left_pwm: int
    right_pwm: int
    duration_ms: int
    confidence: float
    reason_code: str
    safe_to_execute: bool
    backend_latency_ms: int
    model_latency_ms: int


def run_simulation() -> tuple[list[StepLog], UUID, Path]:
    """Run full session simulation through the real backend pipeline."""

    tmp_dir = Path("data/sim_session_v2")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    clear_cached_db_handles()
    settings = AppSettings(
        app_env="simulation",
        log_level="WARNING",
        ollama_model="navigation-stub",
        artifacts_dir=tmp_dir / "artifacts",
        database_url=f"sqlite:///{tmp_dir / 'session_v2.db'}",
        prompt_version="v1",
        quality_min_score=0.0,
        quality_min_blur_score=0.0,
    )

    app = create_app(settings=settings)
    app.state.inference_adapter = NavigationStubAdapter(WAYPOINTS)

    session_id = uuid4()
    steps: list[StepLog] = []

    with TestClient(app) as client:
        for wp in WAYPOINTS:
            frame_bytes = generate_frame(wp)
            ts = int(time.time() * 1000) + wp.seq * 3500  # ~3.5s per frame

            response = client.post(
                "/api/v1/control/frame",
                data={
                    "device_id": "vlmcar-01",
                    "session_id": str(session_id),
                    "seq": str(wp.seq),
                    "timestamp_ms": str(ts),
                    "frame_width": "320",
                    "frame_height": "240",
                    "jpeg_quality": "12",
                    "mode": "AUTO",
                },
                files={"image": ("frame.jpg", frame_bytes, "image/jpeg")},
            )

            assert response.status_code == 200, f"Frame {wp.seq} failed: {response.text}"
            r = response.json()

            step = StepLog(
                seq=wp.seq,
                timestamp_ms=ts,
                scene=wp.scene,
                hazards=wp.hazards,
                expected_action=wp.expected_action,
                actual_action=r["action"],
                action_match=r["action"] == wp.expected_action,
                left_pwm=r["left_pwm"],
                right_pwm=r["right_pwm"],
                duration_ms=r["duration_ms"],
                confidence=r["confidence"],
                reason_code=r["reason_code"],
                safe_to_execute=r["safe_to_execute"],
                backend_latency_ms=r["backend_latency_ms"],
                model_latency_ms=r["model_latency_ms"],
            )
            steps.append(step)

            # Print live progress
            arrow = {
                "FORWARD": "^", "LEFT": "<", "RIGHT": ">", "STOP": "X"
            }.get(r["action"], "?")
            match_mark = "OK" if step.action_match else "MISMATCH"
            print(
                f"  [{wp.seq:02d}] {arrow} {r['action']:7s}  "
                f"PWM L={r['left_pwm']:3d} R={r['right_pwm']:3d}  "
                f"dur={r['duration_ms']:3d}ms  "
                f"conf={r['confidence']:.2f}  "
                f"{r['reason_code']:20s}  [{match_mark}]"
            )

    # Save steps as JSONL
    jsonl_path = tmp_dir / "session_steps.jsonl"
    with open(jsonl_path, "w") as f:
        for step in steps:
            f.write(json.dumps(asdict(step)) + "\n")

    return steps, session_id, tmp_dir


def query_db_summary(db_path: Path, session_id: UUID) -> dict:
    """Pull summary stats from the session database."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM sessions")
    sessions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM frames")
    frames = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM decisions")
    decisions = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM errors")
    errors = cur.fetchone()[0]

    cur.execute("""
        SELECT action, COUNT(*) FROM decisions
        WHERE session_id = ?
        GROUP BY action
    """, (str(session_id),))
    action_dist = dict(cur.fetchall())

    cur.execute("""
        SELECT AVG(confidence), MIN(confidence), MAX(confidence)
        FROM decisions WHERE session_id = ?
    """, (str(session_id),))
    conf_row = cur.fetchone()

    cur.execute("""
        SELECT AVG(backend_latency_ms) FROM decisions WHERE session_id = ?
    """, (str(session_id),))
    avg_latency = cur.fetchone()[0]

    conn.close()
    return {
        "sessions": sessions,
        "frames": frames,
        "decisions": decisions,
        "errors": errors,
        "action_distribution": action_dist,
        "confidence_avg": round(conf_row[0], 3) if conf_row[0] else 0,
        "confidence_min": round(conf_row[1], 3) if conf_row[1] else 0,
        "confidence_max": round(conf_row[2], 3) if conf_row[2] else 0,
        "avg_backend_latency_ms": round(avg_latency, 1) if avg_latency else 0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("VLMcar Session Simulation: Room A -> Room B")
    print("Obstacles: 3 chairs, 3 tables")
    print("=" * 70)
    print()

    print("Running simulation through full backend pipeline...")
    print()
    steps, session_id, data_dir = run_simulation()

    print()
    print("-" * 70)
    print("Session complete.")
    print(f"  Session ID:    {session_id}")
    print(f"  Total frames:  {len(steps)}")
    print(f"  Action match:  {sum(1 for s in steps if s.action_match)}/{len(steps)}")
    print()

    db_path = data_dir / "session_v2.db"
    summary = query_db_summary(db_path, session_id)
    print("Database summary:")
    print(f"  Sessions:      {summary['sessions']}")
    print(f"  Frames:        {summary['frames']}")
    print(f"  Decisions:     {summary['decisions']}")
    print(f"  Errors:        {summary['errors']}")
    print(f"  Actions:       {summary['action_distribution']}")
    print(f"  Confidence:    avg={summary['confidence_avg']} "
          f"min={summary['confidence_min']} max={summary['confidence_max']}")
    print(f"  Avg latency:   {summary['avg_backend_latency_ms']}ms")
    print()

    # Output JSON summary for findingV2.md
    result = {
        "session_id": str(session_id),
        "total_steps": len(steps),
        "action_matches": sum(1 for s in steps if s.action_match),
        "db_summary": summary,
        "steps": [asdict(s) for s in steps],
    }
    result_path = data_dir / "session_result.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Full results saved to: {result_path}")
    print(f"Step log saved to:     {data_dir / 'session_steps.jsonl'}")
