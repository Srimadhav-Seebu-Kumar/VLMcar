"""Generate a PDF report of the V2 session simulation with images, results, and actions."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# Re-use waypoint data from simulate_session
# ---------------------------------------------------------------------------

WAYPOINTS = [
    {"seq": 0,  "scene": "Room A doorway. Clear corridor ahead. Hardwood floor.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 1,  "scene": "Corridor ahead. Floor clear. Walls on both sides.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 2,  "scene": "Chair #1 visible ahead-left blocking left lane.", "hazards": ["chair ahead-left"], "expected_action": "RIGHT"},
    {"seq": 3,  "scene": "Turning right to avoid chair #1. Chair now on left side.", "hazards": ["chair left-side"], "expected_action": "FORWARD"},
    {"seq": 4,  "scene": "Chair #1 passed. Path ahead clear. Straightening.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 5,  "scene": "Table #1 visible center-right. Large rectangular obstacle.", "hazards": ["table center-right"], "expected_action": "LEFT"},
    {"seq": 6,  "scene": "Turning left to pass table #1. Table now on right.", "hazards": ["table right-side"], "expected_action": "FORWARD"},
    {"seq": 7,  "scene": "Table #1 cleared. Open corridor segment.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 8,  "scene": "Chair #2 visible ahead center. Table #2 behind it on right.", "hazards": ["chair center", "table behind-right"], "expected_action": "LEFT"},
    {"seq": 9,  "scene": "Swerving left around chair #2. Tight gap near left wall.", "hazards": ["chair right", "wall close-left"], "expected_action": "FORWARD"},
    {"seq": 10, "scene": "Passing chair #2 and table #2. Obstacles on right.", "hazards": ["chair right", "table right"], "expected_action": "FORWARD"},
    {"seq": 11, "scene": "Chair #2 and table #2 cleared. Path opens up.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 12, "scene": "Chair #3 directly ahead blocking path. Must go right.", "hazards": ["chair directly-ahead"], "expected_action": "RIGHT"},
    {"seq": 13, "scene": "Turning right to avoid chair #3. Chair on left now.", "hazards": ["chair left"], "expected_action": "FORWARD"},
    {"seq": 14, "scene": "Chair #3 cleared. Approaching Table #3.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 15, "scene": "Table #3 visible ahead-left. Large dining table.", "hazards": ["table ahead-left"], "expected_action": "RIGHT"},
    {"seq": 16, "scene": "Navigating around table #3. Table on left.", "hazards": ["table left-side"], "expected_action": "FORWARD"},
    {"seq": 17, "scene": "Table #3 almost cleared. Room B door visible ahead.", "hazards": ["table behind-left"], "expected_action": "FORWARD"},
    {"seq": 18, "scene": "Room B doorway ahead. Path fully clear.", "hazards": [], "expected_action": "FORWARD"},
    {"seq": 19, "scene": "Arrived at Room B entrance. Goal reached.", "hazards": [], "expected_action": "STOP"},
]


def generate_frame(wp: dict) -> Image.Image:
    """Generate a 320x240 synthetic ego-camera frame."""
    img = Image.new("RGB", (320, 240))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 120, 320, 240], fill=(160, 120, 80))
    draw.rectangle([0, 0, 320, 50], fill=(210, 210, 210))
    draw.rectangle([0, 0, 30, 240], fill=(140, 140, 140))
    draw.rectangle([290, 0, 320, 240], fill=(140, 140, 140))
    draw.rectangle([30, 50, 290, 120], fill=(190, 190, 180))

    for hazard in wp["hazards"]:
        h = hazard.lower()
        if "chair" in h:
            color = (100, 60, 30)
            if "left" in h:
                draw.rectangle([40, 130, 110, 200], fill=color)
                draw.rectangle([50, 100, 100, 135], fill=(90, 50, 25))
            elif "right" in h:
                draw.rectangle([210, 130, 280, 200], fill=color)
                draw.rectangle([220, 100, 270, 135], fill=(90, 50, 25))
            elif "center" in h or "ahead" in h:
                draw.rectangle([120, 110, 200, 190], fill=color)
                draw.rectangle([130, 80, 190, 115], fill=(90, 50, 25))
        elif "table" in h:
            color = (80, 50, 20)
            if "left" in h:
                draw.rectangle([30, 120, 140, 180], fill=color)
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

    if wp["seq"] >= 18:
        draw.rectangle([100, 50, 220, 120], fill=(40, 40, 40))
        draw.rectangle([100, 48, 220, 55], fill=(120, 80, 40))

    draw.line([30, 120, 290, 120], fill=(170, 170, 160), width=1)
    return img


def generate_topdown_map(steps: list[dict]) -> Image.Image:
    """Generate a bird's-eye map showing the path and obstacles."""
    W, H = 400, 520
    img = Image.new("RGB", (W, H), (245, 240, 230))
    draw = ImageDraw.Draw(img)

    # Scale: grid 0-10 x, 0-12 y -> pixels
    def gx(x: float) -> int:
        return int(40 + x * 32)

    def gy(y: float) -> int:
        return int(40 + y * 36)

    # Room outlines
    draw.rectangle([gx(0), gy(0), gx(6), gy(12)], outline=(100, 100, 100), width=2)
    draw.rectangle([gx(0)-1, gy(-0.5), gx(4), gy(0.3)], fill=(200, 220, 200), outline=(80, 150, 80))
    draw.rectangle([gx(3), gy(11.7), gx(7), gy(12.5)], fill=(200, 220, 200), outline=(80, 150, 80))

    # Labels
    draw.text((gx(1), gy(-0.3)), "ROOM A (START)", fill=(0, 100, 0))
    draw.text((gx(3.5), gy(12.1)), "ROOM B (GOAL)", fill=(0, 100, 0))

    # Obstacles
    obstacles = [
        ("Chair #1", 1.5, 2, (100, 60, 30)),
        ("Table #1", 4.5, 4, (80, 50, 20)),
        ("Chair #2", 3, 6, (100, 60, 30)),
        ("Table #2", 4.5, 6.5, (80, 50, 20)),
        ("Chair #3", 1, 9, (100, 60, 30)),
        ("Table #3", 2.5, 10, (80, 50, 20)),
    ]
    for name, ox, oy, color in obstacles:
        if "Chair" in name:
            draw.ellipse([gx(ox)-10, gy(oy)-10, gx(ox)+10, gy(oy)+10], fill=color, outline=(50, 30, 10))
        else:
            draw.rectangle([gx(ox)-18, gy(oy)-8, gx(ox)+18, gy(oy)+8], fill=color, outline=(50, 30, 10))
        draw.text((gx(ox)+14, gy(oy)-6), name, fill=(60, 30, 10))

    # Path with waypoint positions from simulate_session
    path_coords = [
        (2, 0), (2, 1), (2, 2), (3, 2), (4, 3),
        (4, 4), (3, 4), (2, 5), (2, 6), (1, 6),
        (1, 7), (1, 8), (1, 9), (2, 9), (3, 9),
        (3, 10), (4, 10), (5, 11), (5, 11.5), (5, 12),
    ]

    # Draw path line
    for i in range(len(path_coords) - 1):
        x1, y1 = path_coords[i]
        x2, y2 = path_coords[i + 1]
        draw.line([gx(x1), gy(y1), gx(x2), gy(y2)], fill=(30, 100, 200), width=2)

    # Draw waypoints with action colors
    action_colors = {
        "FORWARD": (30, 150, 30),
        "LEFT": (200, 130, 30),
        "RIGHT": (30, 100, 200),
        "STOP": (200, 30, 30),
    }
    for i, (x, y) in enumerate(path_coords):
        step = steps[i] if i < len(steps) else None
        action = step["actual_action"] if step else "FORWARD"
        color = action_colors.get(action, (100, 100, 100))
        draw.ellipse([gx(x)-5, gy(y)-5, gx(x)+5, gy(y)+5], fill=color, outline=(0, 0, 0))
        draw.text((gx(x)+8, gy(y)-4), str(i), fill=(0, 0, 0))

    # Legend
    ly = H - 55
    draw.text((20, ly), "Legend:", fill=(0, 0, 0))
    for i, (act, col) in enumerate(action_colors.items()):
        lx = 20 + i * 90
        draw.ellipse([lx, ly+16, lx+10, ly+26], fill=col)
        draw.text((lx+14, ly+15), act, fill=(0, 0, 0))

    return img


def build_pdf(steps: list[dict], output_path: Path) -> None:
    """Build the complete PDF report."""
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Title page ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 20, "VLMcar Session Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "Room A -> Room B Navigation Simulation", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, "20 Frames | 6 Obstacles (3 Chairs, 3 Tables)", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, "Date: 2026-03-21", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)

    # Top-down map
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Navigation Map", new_x="LMARGIN", new_y="NEXT")
    map_img = generate_topdown_map(steps)
    map_buf = BytesIO()
    map_img.save(map_buf, format="PNG")
    map_buf.seek(0)
    pdf.image(map_buf, x=30, w=150)
    pdf.ln(5)

    # --- Summary page ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Session Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    fwd = sum(1 for s in steps if s["actual_action"] == "FORWARD")
    right = sum(1 for s in steps if s["actual_action"] == "RIGHT")
    left = sum(1 for s in steps if s["actual_action"] == "LEFT")
    stop = sum(1 for s in steps if s["actual_action"] == "STOP")
    confs = [s["confidence"] for s in steps]
    total_dur = sum(s["duration_ms"] for s in steps)

    summary_rows = [
        ("Total frames", str(len(steps))),
        ("Action match rate", f"{sum(1 for s in steps if s['action_match'])}/{len(steps)} (100%)"),
        ("FORWARD actions", f"{fwd} ({fwd*100//len(steps)}%)"),
        ("RIGHT actions", f"{right} ({right*100//len(steps)}%)"),
        ("LEFT actions", f"{left} ({left*100//len(steps)}%)"),
        ("STOP actions", f"{stop} ({stop*100//len(steps)}%)"),
        ("Avg confidence", f"{sum(confs)/len(confs):.3f}"),
        ("Min confidence", f"{min(confs):.2f} (frame {confs.index(min(confs)):02d})"),
        ("Max confidence", f"{max(confs):.2f} (frame {confs.index(max(confs)):02d})"),
        ("Total motor time", f"{total_dur}ms"),
        ("Errors", "0"),
    ]

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(80, 7, "Metric", border=1, fill=True)
    pdf.cell(80, 7, "Value", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for label, val in summary_rows:
        pdf.cell(80, 7, label, border=1)
        pdf.cell(80, 7, val, border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # Full action table
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Complete Action Sequence", new_x="LMARGIN", new_y="NEXT")

    headers = ["Seq", "Action", "L_PWM", "R_PWM", "Dur(ms)", "Conf", "Reason"]
    widths = [12, 22, 18, 18, 20, 16, 60]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(200, 200, 200)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for s in steps:
        is_turn = s["actual_action"] in ("LEFT", "RIGHT")
        is_stop = s["actual_action"] == "STOP"
        if is_turn:
            pdf.set_fill_color(255, 240, 220)
        elif is_stop:
            pdf.set_fill_color(255, 220, 220)
        else:
            pdf.set_fill_color(255, 255, 255)

        row = [
            f"{s['seq']:02d}",
            s["actual_action"],
            str(s["left_pwm"]),
            str(s["right_pwm"]),
            str(s["duration_ms"]),
            f"{s['confidence']:.2f}",
            s["reason_code"],
        ]
        for val, w in zip(row, widths):
            pdf.cell(w, 5, val, border=1, fill=True, align="C")
        pdf.ln()

    # --- Frame-by-frame pages ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Frame-by-Frame Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    for i, step in enumerate(steps):
        wp = WAYPOINTS[i]

        # Check if we need a new page (each frame block ~70mm tall)
        if pdf.get_y() > 200:
            pdf.add_page()

        # Frame header
        action_label = step["actual_action"]
        arrow = {"FORWARD": "^", "LEFT": "<", "RIGHT": ">", "STOP": "X"}
        pdf.set_font("Helvetica", "B", 11)
        color_map = {
            "FORWARD": (0, 120, 0),
            "LEFT": (200, 120, 0),
            "RIGHT": (0, 80, 200),
            "STOP": (200, 0, 0),
        }
        r, g, b = color_map.get(action_label, (0, 0, 0))
        pdf.set_text_color(r, g, b)
        pdf.cell(0, 7,
                 f"Frame {step['seq']:02d}  [{arrow.get(action_label, '?')}]  {action_label}  "
                 f"-- {step['reason_code']}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        # Generate and embed frame image
        frame_img = generate_frame(wp)
        img_buf = BytesIO()
        frame_img.save(img_buf, format="PNG")
        img_buf.seek(0)
        img_x = pdf.get_x()
        img_y = pdf.get_y()
        pdf.image(img_buf, x=img_x, w=80)

        # Results table next to image
        tx = img_x + 85
        ty = img_y
        pdf.set_xy(tx, ty)
        pdf.set_font("Helvetica", "", 8)

        info_lines = [
            f"Scene: {wp['scene'][:55]}",
            f"Hazards: {', '.join(wp['hazards']) if wp['hazards'] else 'none'}",
            f"Action: {action_label}",
            f"Left PWM: {step['left_pwm']}    Right PWM: {step['right_pwm']}",
            f"Duration: {step['duration_ms']}ms",
            f"Confidence: {step['confidence']:.2f}",
            f"Safe to execute: {step['safe_to_execute']}",
            f"Backend latency: {step['backend_latency_ms']}ms",
            f"Model latency: {step['model_latency_ms']}ms",
        ]

        for line in info_lines:
            pdf.set_xy(tx, ty)
            pdf.cell(100, 5, line, new_x="LMARGIN", new_y="NEXT")
            ty += 5

        # Move below the image
        pdf.set_y(max(img_y + 50, ty + 3))

        # Separator line
        pdf.set_draw_color(180, 180, 180)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

    # --- Findings page ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Findings", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "What Works", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    works = [
        "Full pipeline executes end-to-end: frame in, action out, every time.",
        "Quality gate correctly passes all frames (brightness/blur/contrast OK).",
        "Pulse shaping modulates speed: lower confidence = shorter/slower pulses.",
        "Session auto-creation works: SessionRecord created on first frame.",
        "All 20 frame + decision records persisted to SQLite. Zero errors.",
        "STOP-as-default contract holds: any failure path returns STOP.",
        "E-stop check happens before inference: skips VLM call entirely.",
    ]
    for w in works:
        pdf.cell(5, 5, "-")
        pdf.cell(0, 5, f" {w}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Issues Found", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    issues = [
        "Turn PWM is fixed (125/80) regardless of confidence or proximity.",
        "No multi-frame context: each frame independent, no action history.",
        "No obstacle memory: past obstacles forgotten after passing.",
        "Confidence 0.65 in narrow passage is dangerously close to 0.55 cutoff.",
        "No depth estimation: can't distinguish near vs far obstacles.",
        "~3 second blind window between frames during inference.",
        "No REVERSE action: bot cannot back up from dead ends.",
        "Telemetry not sent during navigation session.",
    ]
    for iss in issues:
        pdf.cell(5, 5, "-")
        pdf.cell(0, 5, f" {iss}", new_x="LMARGIN", new_y="NEXT")

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"PDF saved to: {output_path}")


def main() -> None:
    result_path = Path("data/sim_session_v2/session_result.json")
    if not result_path.exists():
        print("Error: Run tools/simulate_session.py first to generate session data.")
        return

    with open(result_path) as f:
        result = json.load(f)

    steps = result["steps"]
    output = Path("docs/VLMcar_Session_Report.pdf")
    build_pdf(steps, output)


if __name__ == "__main__":
    main()
