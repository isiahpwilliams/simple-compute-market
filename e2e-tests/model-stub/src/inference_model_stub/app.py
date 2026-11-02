"""The stub's OpenAI-style routes: one model, and replies that depend only on the prompt."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

DEFAULT_MODEL = "stub-model"
DEFAULT_CHUNK_DELAY_SECONDS = 0.05


def reply_to(prompt: str) -> str:
    """The completion for ``prompt``: the same prompt always gets the same reply."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return f"Stub reply {digest[:8]} {digest[8:16]} {digest[16:24]}."


def _prompt_of_chat(body: dict[str, Any]) -> str:
    return "\n".join(str(m.get("content", "")) for m in body.get("messages") or [])


def _prompt_of_completion(body: dict[str, Any]) -> str:
    prompt = body.get("prompt", "")
    return "\n".join(map(str, prompt)) if isinstance(prompt, list) else str(prompt)


def create_app(
    *,
    model: str = DEFAULT_MODEL,
    chunk_delay_seconds: float = DEFAULT_CHUNK_DELAY_SECONDS,
    pause: Callable[[], Awaitable[None]] | None = None,
) -> FastAPI:
    """The stub; ``pause`` runs between streamed chunks, by default a ``chunk_delay_seconds`` sleep."""
    app = FastAPI(title="inference-model-stub")
    between = pause or (lambda: asyncio.sleep(chunk_delay_seconds))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": model, "object": "model", "owned_by": "arkhai"}]}

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> Any:
        return await _complete(await request.json(), chat=True)

    @app.post("/v1/completions")
    async def completions(request: Request) -> Any:
        return await _complete(await request.json(), chat=False)

    async def _complete(body: dict[str, Any], *, chat: bool) -> Any:
        if body.get("model") != model:
            return JSONResponse(
                status_code=404,
                content={"error": {
                    "message": f"model {body.get('model')!r} is not served here",
                    "type": "invalid_request_error",
                    "code": "model_not_found",
                }},
            )
        prompt = _prompt_of_chat(body) if chat else _prompt_of_completion(body)
        reply = reply_to(prompt)
        created = int(time.time())
        ident = f"cmpl-{hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]}"
        kind = "chat.completion" if chat else "text_completion"
        if body.get("stream"):
            return StreamingResponse(
                _stream(reply, ident=ident, created=created, kind=kind, chat=chat),
                media_type="text/event-stream",
            )
        choice: dict[str, Any] = (
            {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
            if chat
            else {"index": 0, "text": reply, "finish_reason": "stop"}
        )
        return {
            "id": ident,
            "object": kind,
            "created": created,
            "model": model,
            "choices": [choice],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(reply.split()),
                "total_tokens": len(prompt.split()) + len(reply.split()),
            },
        }

    async def _stream(
        reply: str, *, ident: str, created: int, kind: str, chat: bool,
    ) -> AsyncIterator[bytes]:
        words = reply.split(" ")
        for index, word in enumerate(words):
            piece = word if index == 0 else f" {word}"
            delta: dict[str, Any] = (
                {"index": 0, "delta": {"content": piece}, "finish_reason": None}
                if chat
                else {"index": 0, "text": piece, "finish_reason": None}
            )
            chunk = {"id": ident, "object": f"{kind}.chunk", "created": created, "model": model, "choices": [delta]}
            yield f"data: {json.dumps(chunk)}\n\n".encode()
            await between()
        yield b"data: [DONE]\n\n"

    return app


app = create_app(
    model=os.environ.get("MODEL_STUB_MODEL", DEFAULT_MODEL),
    chunk_delay_seconds=float(
        os.environ.get("MODEL_STUB_CHUNK_DELAY_SECONDS", DEFAULT_CHUNK_DELAY_SECONDS),
    ),
)
