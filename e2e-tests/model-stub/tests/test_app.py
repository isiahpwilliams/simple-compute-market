"""The stub over ASGI: its model list, exact replies, streaming order, and refusal of other models."""

from __future__ import annotations

import json
import time

import httpx
import pytest

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


async def test_a_streamed_reply_arrives_in_order_before_it_finishes(client):
    body = {"model": MODEL, "messages": [{"role": "user", "content": "hello"}], "stream": True}
    arrivals: list[tuple[float, str]] = []

    async with client.stream("POST", "/v1/chat/completions", json=body) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                arrivals.append((time.monotonic(), line.removeprefix("data: ")))

    assert arrivals[-1][1] == "[DONE]"
    pieces = [json.loads(data)["choices"][0]["delta"]["content"] for _, data in arrivals[:-1]]
    assert "".join(pieces) == reply_to("hello")
    assert arrivals[0][0] < arrivals[-1][0]


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/completions"])
async def test_another_model_is_refused_404(client, path):
    response = await client.post(path, json={"model": "other", "prompt": "hi", "messages": []})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
