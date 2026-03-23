from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from backend.app.schemas.enums import Action


class ParseError(RuntimeError):
    """Raised when model output cannot be parsed into safe structured decision."""


@dataclass(frozen=True)
class ParsedDecision:
    """Structured model decision after schema validation."""

    action: Action
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

        try:
            validate(instance=payload, schema=self._schema)
        except ValidationError as exc:
            raise ParseError(f"model output failed schema validation: {exc.message}") from exc

        try:
            action = Action(payload["action"])
        except ValueError as exc:
            raise ParseError(f"invalid action value: {payload.get('action')}") from exc

        return ParsedDecision(
            action=action,
            confidence=float(payload["confidence"]),
            reason_code=str(payload.get("reason_code", action.value)),
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
