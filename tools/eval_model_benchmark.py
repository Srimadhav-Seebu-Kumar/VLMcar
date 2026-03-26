"""Benchmark any Ollama vision model against the 10-scenario evaluation suite.

Usage:
    python tools/eval_model_benchmark.py --model gemma3:4b
    python tools/eval_model_benchmark.py --model llava --prompt-version v4 --cv
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = REPO_ROOT / "docs" / "findings" / "v3_eval"
PROMPTS_DIR = REPO_ROOT / "prompts"
OUTPUT_DIR = REPO_ROOT / "docs" / "findings" / "v5_model_benchmark"

GROUND_TRUTH: dict[str, str] = {
    "01_clear_corridor": "FORWARD",
    "02_dead_end": "STOP",
    "03_obstacle_right": "LEFT",
    "04_obstacle_left": "RIGHT",
    "05_narrow_passage": "FORWARD",
    "06_center_block": "LEFT",
    "07_person_ahead": "STOP",
    "08_cluttered_left": "RIGHT",
    "09_close_obstacle": "STOP",
    "10_cone_chair": "LEFT",
}


def load_prompt(version: str) -> str:
    sys_versioned = PROMPTS_DIR / f"system_prompt_{version}.txt"
    sys_default = PROMPTS_DIR / "system_prompt.txt"
    sys_path = sys_versioned if sys_versioned.exists() else sys_default
    system = sys_path.read_text(encoding="utf-8").strip()
    decision = (PROMPTS_DIR / f"decision_prompt_{version}.txt").read_text(encoding="utf-8").strip()
    return f"{system}\n\n{decision}"


def load_schema(version: str) -> dict:
    versioned = PROMPTS_DIR / f"json_schema_decision_{version}.json"
    default = PROMPTS_DIR / "json_schema_decision.json"
    path = versioned if versioned.exists() else default
    schema = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in schema.items() if not k.startswith("$")}


def detect_obstacles_cv(image_bytes: bytes) -> dict | None:
    """Run OpenCV obstacle zone detection if available."""
    try:
        from backend.app.services.cv_obstacle_detector import detect_obstacle_zones
        return detect_obstacle_zones(image_bytes)
    except (ImportError, ModuleNotFoundError):
        return None


def run_inference(
    model: str,
    prompt: str,
    image_bytes: bytes,
    schema: dict,
    ollama_url: str = "http://127.0.0.1:11434",
    timeout: int = 120,
) -> tuple[dict, float]:
    """Call Ollama and return (parsed_json, latency_seconds)."""
    img_b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0},
    }
    t0 = time.perf_counter()
    with httpx.Client(base_url=ollama_url, timeout=timeout) as client:
        resp = client.post("/api/generate", json=payload)
    latency = time.perf_counter() - t0

    body = resp.json()
    raw = body.get("response", "")
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = {"action": "ERROR", "confidence": 0}
    return parsed, latency


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Ollama vision models")
    parser.add_argument("--model", required=True, help="Ollama model name (e.g. gemma3:4b)")
    parser.add_argument("--prompt-version", default="v3", help="Prompt version (v3, v4)")
    parser.add_argument("--cv", action="store_true", help="Enable CV obstacle detection metadata")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prompt_text = load_prompt(args.prompt_version)
    schema = load_schema(args.prompt_version)

    print(f"Model:   {args.model}")
    print(f"Prompt:  {args.prompt_version}")
    print(f"CV:      {'ON' if args.cv else 'OFF'}")
    print(f"Schema:  {list(schema.get('properties', {}).keys())}")
    print(f"{'='*70}")

    results = []
    total_correct = 0
    total_latency = 0.0

    for scenario, expected in GROUND_TRUTH.items():
        img_path = EVAL_DIR / f"{scenario}.jpg"
        if not img_path.exists():
            print(f"[SKIP] {scenario} -- image not found")
            continue

        image_bytes = img_path.read_bytes()

        # Build full prompt with optional CV metadata
        full_prompt = prompt_text
        if args.cv:
            cv_data = detect_obstacles_cv(image_bytes)
            if cv_data:
                full_prompt += f"\n\nOBSTACLE SENSOR DATA:\n{json.dumps(cv_data)}"

        parsed, latency = run_inference(
            model=args.model,
            prompt=full_prompt,
            image_bytes=image_bytes,
            schema=schema,
            ollama_url=args.ollama_url,
            timeout=args.timeout,
        )

        action = parsed.get("action", "ERROR")
        confidence = parsed.get("confidence", 0)
        correct = action == expected
        if correct:
            total_correct += 1
        total_latency += latency

        mark = "\033[32mPASS\033[0m" if correct else "\033[31mFAIL\033[0m"
        print(f"[{mark}] {scenario:25s} expected={expected:8s} got={action:8s} conf={confidence:.2f} time={latency:.2f}s")

        results.append({
            "scenario": scenario,
            "expected": expected,
            "actual": action,
            "confidence": confidence,
            "correct": correct,
            "latency_s": round(latency, 3),
            "raw_output": json.dumps(parsed),
        })

    n = len(results)
    accuracy = total_correct / n if n else 0
    avg_latency = total_latency / n if n else 0

    print(f"{'='*70}")
    print(f"ACCURACY: {total_correct}/{n} ({accuracy*100:.0f}%)")
    print(f"AVG LATENCY: {avg_latency:.2f}s")

    # Action distribution
    from collections import Counter
    dist = Counter(r["actual"] for r in results)
    print(f"DISTRIBUTION: {dict(dist)}")

    # Save results
    safe_model = args.model.replace(":", "_").replace("/", "_")
    cv_tag = "_cv" if args.cv else ""
    out_file = OUTPUT_DIR / f"{safe_model}_{args.prompt_version}{cv_tag}.json"
    output = {
        "model": args.model,
        "prompt_version": args.prompt_version,
        "cv_enabled": args.cv,
        "accuracy": f"{total_correct}/{n}",
        "accuracy_pct": round(accuracy * 100, 1),
        "avg_latency_s": round(avg_latency, 3),
        "action_distribution": dict(dist),
        "results": results,
    }
    out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    main()
