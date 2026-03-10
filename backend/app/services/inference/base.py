from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class InferenceError(RuntimeError):
    """Raised when the model adapter cannot produce a usable result."""


@dataclass(frozen=True)
class InferenceRequest:
    """Inference input payload consumed by adapter implementations."""

    prompt: str
    image_bytes: bytes
    trace_id: UUID
    session_id: UUID


@dataclass(frozen=True)
class InferenceResult:
    """Normalized model adapter output for downstream parsing."""

    raw_output: str
    model_latency_ms: int
    provider_payload: dict[str, object]


class InferenceAdapter(Protocol):
    """Contract for pluggable local vision-language model adapters."""

    async def infer(self, request: InferenceRequest) -> InferenceResult:
        """Run model inference and return normalized output."""
