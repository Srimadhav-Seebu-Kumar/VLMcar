from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from backend.app.services.inference.base import InferenceError, InferenceRequest, InferenceResult


class OllamaNativeAdapter:
    """Native Ollama `/api/generate` adapter for local vision inference."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: int,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._http_client = http_client

    async def infer(self, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        payload = {
            "model": self._model,
            "prompt": request.prompt,
            "images": [base64.b64encode(request.image_bytes).decode("ascii")],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }

        response_json = await self._post_generate(payload)
        raw_output = response_json.get("response")
        if not isinstance(raw_output, str) or not raw_output.strip():
            raise InferenceError("ollama response missing textual `response` field")

        latency_ms = int((time.perf_counter() - started) * 1000)
        return InferenceResult(
            raw_output=raw_output.strip(),
            model_latency_ms=latency_ms,
            provider_payload=response_json,
        )

    async def _post_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._http_client is not None:
            return await self._execute_request(self._http_client, payload)

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout_s) as client:
            return await self._execute_request(client, payload)

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await client.post("/api/generate", json=payload)
        except httpx.HTTPError as exc:
            raise InferenceError(f"ollama request failed: {exc}") from exc

        if response.status_code != 200:
            raise InferenceError(f"ollama returned status {response.status_code}")

        try:
            body: dict[str, Any] = response.json()
        except ValueError as exc:
            raise InferenceError("ollama returned invalid JSON") from exc

        return body
