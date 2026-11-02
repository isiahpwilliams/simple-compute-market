"""The inference gateway's entry point: not ready until its listing loads, then the family gateway."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from arkhai_api_gate import GateConfig, TokensClient
from arkhai_api_gateway import admit_all, create_gateway_app
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from storefront_client.client import StorefrontClient

from inference_gateway_service.config import GatewaySettings, gate_config
from inference_gateway_service.offering import load_offering

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class GatewayService:
    """Answers ``503`` until ``load`` builds the gateway, retrying it, then serves the gateway.

    The gateway can start before the storefront has published its listing, so
    a refusal is reported by ``/health`` and retried rather than fatal.
    """

    def __init__(self, load: Callable[[], Awaitable[FastAPI]], *, retry_seconds: float) -> None:
        self._load = load
        self._retry_seconds = retry_seconds
        self._app: FastAPI | None = None
        self._reason = "the listing has not loaded yet"
        self._loader: asyncio.Task[None] | None = None
        self._running: contextlib.AbstractAsyncContextManager[Any] | None = None
        #: Set once the gateway serves, and once any load is refused.
        self.loaded = asyncio.Event()
        self.refused = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self._app is not None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(receive, send)
        elif self._app is not None:
            await self._app(scope, receive, send)
        elif scope["type"] == "http":
            response = JSONResponse({"status": "not_ready", "reason": self._reason}, status_code=503)
            await response(scope, receive, send)

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                self._loader = asyncio.ensure_future(self._load_until_ready())
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                try:
                    await self._stop()
                except Exception as error:  # noqa: BLE001 — reported as the shutdown's failure
                    await send({"type": "lifespan.shutdown.failed", "message": repr(error)})
                else:
                    await send({"type": "lifespan.shutdown.complete"})
                return

    async def _load_until_ready(self) -> None:
        while True:
            try:
                app = await self._load()
            except Exception as error:  # noqa: BLE001 — reported by /health and retried
                self._reason = str(error) or repr(error)
                self.refused.set()
                await asyncio.sleep(self._retry_seconds)
                continue
            running = app.router.lifespan_context(app)
            await running.__aenter__()
            self._running = running
            self._app = app
            self.loaded.set()
            return

    async def _stop(self) -> None:
        if self._loader is not None and not self._loader.done():
            self._loader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loader
        if self._running is not None:
            running, self._running = self._running, None
            await running.__aexit__(None, None, None)


def create_app(
    settings: GatewaySettings | None = None,
    gate: GateConfig | None = None,
    *,
    storefront_transport: httpx.AsyncBaseTransport | None = None,
    authority: TokensClient | None = None,
    http: httpx.AsyncClient | None = None,
) -> GatewayService:
    """The gateway for the listing ``settings`` names, signing toward its authority as ``service``."""
    settings = settings or GatewaySettings.from_env()
    gate = gate or gate_config()
    if authority is None and not gate.signing_enabled:
        raise ValueError("the gateway signs toward its authority: no identity credential is configured")

    async def load() -> FastAPI:
        storefront = StorefrontClient(settings.storefront_url, transport=storefront_transport)
        try:
            offering = await load_offering(settings, storefront)
        finally:
            await storefront.close()
        return create_gateway_app(offering, gate, authority=authority, verification=admit_all, http=http)

    return GatewayService(load, retry_seconds=settings.listing_retry_seconds)
