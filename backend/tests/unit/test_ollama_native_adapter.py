from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from backend.app.services.inference import InferenceError, InferenceRequest
from backend.app.services.inference.ollama_native import OllamaNativeAdapter


def test_ollama_adapter_builds_request_and_parses_response() -> None:
    captured_payload: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_payload
        captured_payload = json.loads(request.content.decode("utf-8"))
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": '{"action":"STOP"}'})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url="http://test", transport=transport)
    adapter = OllamaNativeAdapter(
        base_url="http://test",
        model="llava",
        timeout_s=10,
        http_client=async_client,
    )

    result = asyncio.run(
        adapter.infer(
            InferenceRequest(
                prompt="decide",
                image_bytes=b"jpeg-bytes",
                trace_id=uuid4(),
                session_id=uuid4(),
            )
        )
    )
    asyncio.run(async_client.aclose())

    assert result.raw_output == '{"action":"STOP"}'
    assert result.model_latency_ms >= 0
    assert captured_payload["model"] == "llava"
    assert captured_payload["stream"] is False


def test_ollama_adapter_raises_on_non_200_status() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url="http://test", transport=transport)
    adapter = OllamaNativeAdapter(
        base_url="http://test",
        model="llava",
        timeout_s=10,
        http_client=async_client,
    )

    with pytest.raises(InferenceError):
        asyncio.run(
            adapter.infer(
                InferenceRequest(
                    prompt="decide",
                    image_bytes=b"jpeg-bytes",
                    trace_id=uuid4(),
                    session_id=uuid4(),
                )
            )
        )
    asyncio.run(async_client.aclose())


def test_ollama_adapter_raises_when_response_field_missing() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"done": True})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(base_url="http://test", transport=transport)
    adapter = OllamaNativeAdapter(
        base_url="http://test",
        model="llava",
        timeout_s=10,
        http_client=async_client,
    )

    with pytest.raises(InferenceError):
        asyncio.run(
            adapter.infer(
                InferenceRequest(
                    prompt="decide",
                    image_bytes=b"jpeg-bytes",
                    trace_id=uuid4(),
                    session_id=uuid4(),
                )
            )
        )
    asyncio.run(async_client.aclose())
