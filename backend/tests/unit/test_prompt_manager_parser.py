from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.schemas import DeviceMode, FrameRequest
from backend.app.services.inference import ParseError, PromptManager, StructuredOutputParser


def prompts_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "prompts"


def test_prompt_manager_builds_versioned_prompt() -> None:
    manager = PromptManager(prompts_dir=prompts_dir())
    frame = FrameRequest(
        device_id="rc-car-01",
        session_id=None,
        seq=1,
        timestamp_ms=1710000000000,
        frame_width=320,
        frame_height=240,
        jpeg_quality=12,
        battery_mv=None,
        mode=DeviceMode.AUTO,
    )

    bundle = manager.build_prompt(frame=frame, prompt_version="v1")

    assert bundle.version == "v1"
    assert "Frame metadata" in bundle.text
    assert "rc-car-01" in bundle.text


def test_prompt_manager_raises_for_missing_prompt_file(tmp_path: Path) -> None:
    (tmp_path / "system_prompt.txt").write_text("system", encoding="utf-8")
    manager = PromptManager(prompts_dir=tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.load_decision_prompt("v9")


def test_structured_parser_parses_valid_json_v5() -> None:
    parser = StructuredOutputParser(schema_path=prompts_dir() / "json_schema_decision_v5.json")
    parsed = parser.parse(
        '{"left_zone":"CLEAR","center_zone":"CLEAR","right_zone":"BLOCKED","heading_deg":0,"throttle":0.8,"confidence":0.91}'
    )

    assert parsed.heading_deg == 0
    assert parsed.throttle == 0.8
    assert parsed.confidence == 0.91


def test_structured_parser_handles_markdown_wrapped_json_v5() -> None:
    parser = StructuredOutputParser(schema_path=prompts_dir() / "json_schema_decision_v5.json")
    parsed = parser.parse(
        """```json
{"left_zone":"CLEAR","center_zone":"BLOCKED","right_zone":"CLEAR","heading_deg":-45,"throttle":0.5,"confidence":0.6}
```"""
    )

    assert parsed.heading_deg == -45
    assert parsed.throttle == 0.5


def test_structured_parser_rejects_invalid_heading_v5() -> None:
    parser = StructuredOutputParser(schema_path=prompts_dir() / "json_schema_decision_v5.json")

    with pytest.raises(ParseError):
        parser.parse(
            '{"left_zone":"CLEAR","center_zone":"CLEAR","right_zone":"CLEAR","heading_deg":-100,"throttle":0.9,"confidence":0.9}'
        )
