from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from simulator.control_client import BackendControlClient
from simulator.episode import EpisodeConfig, run_episode
from simulator.maps import list_builtin_maps
from simulator.replay import ReplayConfig, replay_episode
from simulator.webcam import WebcamConfig, run_webcam_loop


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RC car simulator and webcam runners")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-maps", help="List available simulator maps")

    episode_parser = subparsers.add_parser("episode", help="Run one simulated backend episode")
    _add_common_backend_flags(episode_parser)
    episode_parser.add_argument(
        "--map",
        dest="map_name",
        default=os.getenv("SIM_MAP_NAME", "straight_corridor"),
        help="Built-in simulator map name",
    )
    episode_parser.add_argument(
        "--max-steps",
        type=int,
        default=int(os.getenv("SIM_MAX_STEPS", "40")),
    )
    episode_parser.add_argument(
        "--output-root",
        default=os.getenv("SIM_OUTPUT_DIR", "./tmp_artifacts/sim_runs"),
    )
    episode_parser.add_argument("--frame-width", type=int, default=int(os.getenv("SIM_FRAME_WIDTH", "320")))
    episode_parser.add_argument(
        "--frame-height", type=int, default=int(os.getenv("SIM_FRAME_HEIGHT", "240"))
    )
    episode_parser.add_argument(
        "--jpeg-quality", type=int, default=int(os.getenv("SIM_JPEG_QUALITY", "80"))
    )
    episode_parser.add_argument(
        "--save-topdown",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SIM_SAVE_TOPDOWN", True),
    )
    episode_parser.add_argument(
        "--stop-on-backend-stop",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SIM_STOP_ON_BACKEND_STOP", True),
    )
    episode_parser.add_argument(
        "--sleep-per-step-s",
        type=float,
        default=float(os.getenv("SIM_SLEEP_PER_STEP_S", "0.0")),
    )

    replay_parser = subparsers.add_parser("replay", help="Replay saved simulator frames against backend")
    _add_common_backend_flags(replay_parser)
    replay_parser.add_argument("--steps-jsonl", required=True)
    replay_parser.add_argument(
        "--output-jsonl",
        default=os.getenv("SIM_REPLAY_OUTPUT", "./tmp_artifacts/sim_runs/replay_results.jsonl"),
    )
    replay_parser.add_argument(
        "--jpeg-quality", type=int, default=int(os.getenv("SIM_JPEG_QUALITY", "80"))
    )
    replay_parser.add_argument(
        "--stop-on-backend-stop",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SIM_STOP_ON_BACKEND_STOP", True),
    )

    webcam_parser = subparsers.add_parser("webcam", help="Run real-world laptop camera backend loop")
    _add_common_backend_flags(webcam_parser)
    webcam_parser.add_argument(
        "--camera-index", type=int, default=int(os.getenv("SIM_CAMERA_INDEX", "0"))
    )
    webcam_parser.add_argument(
        "--frame-width", type=int, default=int(os.getenv("SIM_CAMERA_WIDTH", "640"))
    )
    webcam_parser.add_argument(
        "--frame-height", type=int, default=int(os.getenv("SIM_CAMERA_HEIGHT", "480"))
    )
    webcam_parser.add_argument(
        "--jpeg-quality", type=int, default=int(os.getenv("SIM_JPEG_QUALITY", "80"))
    )
    webcam_parser.add_argument(
        "--max-frames",
        type=int,
        default=int(os.getenv("SIM_CAMERA_MAX_FRAMES", "200")),
    )
    webcam_parser.add_argument(
        "--show-preview",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SIM_CAMERA_PREVIEW", False),
    )
    webcam_parser.add_argument(
        "--stop-on-backend-stop",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("SIM_STOP_ON_BACKEND_STOP", True),
    )
    webcam_parser.add_argument(
        "--sleep-per-frame-s",
        type=float,
        default=float(os.getenv("SIM_SLEEP_PER_FRAME_S", "0.0")),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "list-maps":
        payload = [
            {"name": map_def.name, "description": map_def.description}
            for map_def in list_builtin_maps()
        ]
        print(json.dumps(payload, indent=2))
        return

    with BackendControlClient(
        frame_url=args.frame_url,
        timeout_s=args.timeout_s,
        api_key=args.api_key,
    ) as client:
        if args.command == "episode":
            episode_result = run_episode(
                config=EpisodeConfig(
                    map_name=args.map_name,
                    max_steps=args.max_steps,
                    output_root=Path(args.output_root),
                    frame_width=args.frame_width,
                    frame_height=args.frame_height,
                    jpeg_quality=args.jpeg_quality,
                    device_id=args.device_id,
                    save_topdown=args.save_topdown,
                    sleep_per_step_s=args.sleep_per_step_s,
                    stop_on_backend_stop=args.stop_on_backend_stop,
                ),
                control_client=client,
            )
            print(json.dumps(episode_result.as_dict(), indent=2))
            return

        if args.command == "replay":
            replay_result = replay_episode(
                config=ReplayConfig(
                    steps_jsonl_path=Path(args.steps_jsonl),
                    output_jsonl_path=Path(args.output_jsonl),
                    device_id=args.device_id,
                    jpeg_quality=args.jpeg_quality,
                    stop_on_backend_stop=args.stop_on_backend_stop,
                ),
                control_client=client,
            )
            print(json.dumps(replay_result.as_dict(), indent=2))
            return

        if args.command == "webcam":
            webcam_result = run_webcam_loop(
                config=WebcamConfig(
                    device_id=args.device_id,
                    camera_index=args.camera_index,
                    frame_width=args.frame_width,
                    frame_height=args.frame_height,
                    jpeg_quality=args.jpeg_quality,
                    max_frames=args.max_frames,
                    stop_on_backend_stop=args.stop_on_backend_stop,
                    show_preview=args.show_preview,
                    sleep_per_frame_s=args.sleep_per_frame_s,
                ),
                control_client=client,
            )
            print(json.dumps(webcam_result.as_dict(), indent=2))
            return

    raise RuntimeError(f"unsupported command: {args.command}")


def _add_common_backend_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--frame-url",
        default=os.getenv("SIM_BACKEND_FRAME_URL", "http://127.0.0.1:8000/api/v1/control/frame"),
    )
    parser.add_argument(
        "--device-id",
        default=os.getenv("SIM_DEVICE_ID", "sim-edge-01"),
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=float(os.getenv("SIM_BACKEND_TIMEOUT_S", "10.0")),
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("BACKEND_API_KEY", ""),
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
