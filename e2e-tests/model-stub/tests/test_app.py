"""The stub: its model list, exact replies, streaming order, and refusal of other models."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn

from inference_model_stub.app import create_app, reply_to

MODEL = "stub-model"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=create_app(model=MODEL, chunk_delay_seconds=0.05))
    async with httpx.AsyncClient(transport=transport, base_url="http://stub") as client:
        yield client


async def test_the_model_list_names_the_configured_model(client):
    response = await client.get("/v1/models")

    assert [m["id"] for m in response.json()["data"]] == [MODEL]


async def test_a_known_prompt_gets_the_same_exact_reply(client):
    body = {"model": MODEL, "messages": [{"role": "user", "content": "hello"}]}

    first = (await client.post("/v1/chat/completions", json=body)).json()
    second = (await client.post("/v1/chat/completions", json=body)).json()

    assert first["choices"][0]["message"]["content"] == reply_to("hello")
    assert second["choices"] == first["choices"]
    completion = await client.post("/v1/completions", json={"model": MODEL, "prompt": "hello"})
    assert completion.json()["choices"][0]["text"] == reply_to("hello")


@contextlib.asynccontextmanager
async def _served(app) -> AsyncIterator[str]:
    """``app`` on a socket in this event loop; ``ASGITransport`` collects a body before returning it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
    serving = asyncio.ensure_future(server.serve(sockets=[sock]))
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        await serving
        sock.close()


async def test_a_streamed_reply_arrives_in_order_before_it_finishes():
    release = asyncio.Event()
    pauses: list[None] = []

    async def pause() -> None:
        pauses.append(None)
        await release.wait()

    body = {"model": MODEL, "messages": [{"role": "user", "content": "hello"}], "stream": True}
    async with _served(create_app(model=MODEL, pause=pause)) as base_url:
        async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
            async with client.stream("POST", "/v1/chat/completions", json=body) as response:
                lines = response.aiter_lines()
                first = await anext(lines)
                # The stub is held after its first chunk, so the first event arrived alone.
                assert len(pauses) == 1
                release.set()
                rest = [line async for line in lines if line]

    events = [first.removeprefix("data: "), *(line.removeprefix("data: ") for line in rest)]
    assert events[-1] == "[DONE]"
    pieces = [json.loads(data)["choices"][0]["delta"]["content"] for data in events[:-1]]
    assert "".join(pieces) == reply_to("hello")


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/completions"])
async def test_another_model_is_refused_404(client, path):
    response = await client.post(path, json={"model": "other", "prompt": "hi", "messages": []})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
