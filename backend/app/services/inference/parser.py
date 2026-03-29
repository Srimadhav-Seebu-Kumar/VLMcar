from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

logger = logging.getLogger(__name__)

# v4 discrete action → continuous heading/throttle mapping
_ACTION_MAP: dict[str, tuple[int, float]] = {
    "FORWARD": (0, 0.8),
    "LEFT": (-45, 0.5),
    "RIGHT": (45, 0.5),
    "STOP": (0, 0.0),
}


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
        logger.debug("parser_extracted_json", extra={"keys": list(payload.keys())})

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

        # Convert v4 discrete action to continuous heading/throttle if needed
        if "action" in payload and "heading_deg" not in payload:
            payload = self._convert_action_to_continuous(payload)

        heading_deg = int(payload.get("heading_deg", 0))
        throttle = float(payload.get("throttle", 0.0))

        # Clamp values to safe ranges
        heading_deg = max(-90, min(90, heading_deg))
        throttle = max(0.0, min(1.0, throttle))

        logger.info(
            "parser_decision",
            extra={
                "heading_deg": heading_deg,
                "throttle": throttle,
                "confidence": float(payload.get("confidence", 0)),
                "has_action_field": "action" in payload,
                "schema": self._schema_path.name,
            },
        )

        return ParsedDecision(
            heading_deg=heading_deg,
            throttle=throttle,
            confidence=float(payload["confidence"]),
            reason_code=str(payload.get("reason_code", "MODEL_DECISION")),
            scene_summary=str(payload.get("scene_summary", "")),
            hazards=[str(item) for item in payload.get("hazards", [])],
            raw_json=payload,
        )

    def _convert_action_to_continuous(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Convert v4 discrete action to continuous heading_deg + throttle."""
        action = str(payload.get("action", "STOP")).upper()
        heading_deg, throttle = _ACTION_MAP.get(action, (0, 0.0))
        converted = dict(payload)
        converted["heading_deg"] = heading_deg
        converted["throttle"] = throttle
        logger.warning(
            "v4_action_converted",
            extra={
                "action": action,
                "heading_deg": heading_deg,
                "throttle": throttle,
            },
        )
        return converted

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

        logger.error(
            "parser_no_json_found",
            extra={"raw_length": len(text), "raw_preview": text[:200]},
        )
        raise ParseError("could not extract JSON object from model output")

    def _strip_markdown_fence(self, text: str) -> str:
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        return "\n".join(lines).strip()
