from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backend.app.schemas.frame import FrameRequest


@dataclass(frozen=True)
class PromptBundle:
    """Resolved prompt payload sent to the model adapter."""

    version: str
    text: str


class PromptManager:
    """Load and assemble versioned prompt templates from repository files."""

    def __init__(self, prompts_dir: Path) -> None:
        self._prompts_dir = prompts_dir
        self._system_prompts: dict[str, str] = {}
        self._decision_prompts: dict[str, str] = {}

    def load_system_prompt(self, version: str = "default") -> str:
        if version not in self._system_prompts:
            versioned = self._prompts_dir / f"system_prompt_{version}.txt"
            filename = f"system_prompt_{version}.txt" if versioned.exists() else "system_prompt.txt"
            self._system_prompts[version] = self._read_file(filename)
        return self._system_prompts[version]

    def load_decision_prompt(self, version: str = "v1") -> str:
        if version not in self._decision_prompts:
            self._decision_prompts[version] = self._read_file(f"decision_prompt_{version}.txt")
        return self._decision_prompts[version]

    def build_prompt(self, frame: FrameRequest, prompt_version: str = "v1") -> PromptBundle:
        """Combine system and decision prompts with compact frame metadata context."""

        system_prompt = self.load_system_prompt(version=prompt_version)
        decision_prompt = self.load_decision_prompt(prompt_version)
        metadata = {
            "device_id": frame.device_id,
            "seq": frame.seq,
            "mode": frame.mode.value,
            "frame_width": frame.frame_width,
            "frame_height": frame.frame_height,
            "timestamp_ms": frame.timestamp_ms,
        }
        text = "\n\n".join(
            [
                system_prompt,
                decision_prompt,
                "Frame metadata:",
                json.dumps(metadata, separators=(",", ":")),
            ]
        )
        return PromptBundle(version=prompt_version, text=text)

    def _read_file(self, filename: str) -> str:
        path = self._prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()
