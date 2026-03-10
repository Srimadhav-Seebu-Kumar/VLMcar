from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for structured backend logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("trace_id", "session_id", "device_id", "route"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(log_level: str) -> None:
    """Configure process logging with JSON output to stdout."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    logging.basicConfig(level=log_level.upper(), handlers=[handler], force=True)
