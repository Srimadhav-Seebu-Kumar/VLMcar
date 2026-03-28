from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate


class ParseError(RuntimeError):
    """Raised when model output cannot be parsed into safe structured decision."""


@dataclass(frozen=True)
class ParsedDecision:
    """Structured model decision after schema validation.

    Uses continuous heading + throttle instead of discrete actions.
    """

    heading_deg: int
    throttle: float
    confidence: float
    reason_code: str
    scene_summary: str
    hazards: list[str]
    raw_json: dict[str, Any]


class StructuredOutputParser:
    """Parse and validate model output against strict JSON schema."""

    def __init__(self, schema_path: Path) -> None:
        self._schema_path = schema_path
        self._schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def parse(self, raw_output: str) -> ParsedDecision:
        payload = self._extract_json(raw_output)

        # Normalize confidence from percentage (0-100) to fraction (0-1) if needed
        if "confidence" in payload and isinstance(payload["confidence"], (int, float)):
            if payload["confidence"] > 1:
                payload["confidence"] = round(payload["confidence"] / 100, 2)

        # Normalize throttle from percentage (0-100) to fraction (0-1) if needed
        if "throttle" in payload and isinstance(payload["throttle"], (int, float)):
            if payload["throttle"] > 1:
                payload["throttle"] = round(payload["throttle"] / 100, 2)

        try:
            validate(instance=payload, schema=self._schema)
        except ValidationError as exc:
            raise ParseError(f"model output failed schema validation: {exc.message}") from exc

        heading_deg = int(payload.get("heading_deg", 0))
        throttle = float(payload.get("throttle", 0.0))

        # Clamp values to safe ranges
        heading_deg = max(-90, min(90, heading_deg))
        throttle = max(0.0, min(1.0, throttle))

        return ParsedDecision(
            heading_deg=heading_deg,
            throttle=throttle,
            confidence=float(payload["confidence"]),
            reason_code=str(payload.get("reason_code", "MODEL_DECISION")),
            scene_summary=str(payload.get("scene_summary", "")),
            hazards=[str(item) for item in payload.get("hazards", [])],
            raw_json=payload,
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        normalized = text.strip()
        if normalized.startswith("```"):
            normalized = self._strip_markdown_fence(normalized)

        decoder = json.JSONDecoder()
        for index, char in enumerate(normalized):
            if char != "{":
                continue
            try:
                payload, _end = decoder.raw_decode(normalized[index:])
            except JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

        raise ParseError("could not extract JSON object from model output")

    def _strip_markdown_fence(self, text: str) -> str:
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
