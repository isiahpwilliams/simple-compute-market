"""The gateway projected from a fixture listing, charging the real inference service in process.

The storefront and the model server are scripted at their HTTP boundaries.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from arkhai_api.issuance import KeyDisposition, accepted_terms_digest, issuance_request
from arkhai_api_client import AuthorityClient
from arkhai_api_gate import GateConfig, TokensClient
from arkhai_api_gate.signing import AuthoritySigning, build_trusted_authorities
from arkhai_inference.label import INFERENCE_LABEL
from arkhai_inference.listings import InferenceModelCard, accepted_terms
from market_identity import Identity, TrustedIdentitySet
from market_site_client.client import SiteCapacityAdminClient

from inference_gateway_service.config import AUTHORITY_LABEL
from inference_gateway_service.main import GatewayService, create_app
from tests.cards import QUOTA, REGISTRY_URL, SERVED_MODEL, STOREFRONT_URL, Storefront, card, listing, settings
from tests.integration.authority import AUTHORITY, GATEWAY_SIGNER, STOREFRONT_SIGNER, load_authority, unload_authority

AUTHORITY_URL = "http://inference-service"
OTHER_MODEL = "other-instruct"
OTHER_QUOTA = "other-instruct-quota"
# Deterministic development principal; never used on any network.
BUYER = Identity(scheme="eip191", identifier="0xabcdef0000000000000000000000000000000001")


@pytest.fixture
async def authority(tmp_path: Path, monkeypatch):
    app = load_authority(tmp_path, monkeypatch)
    try:
        admin = SiteCapacityAdminClient(
            AUTHORITY_URL, signer=STOREFRONT_SIGNER, expected_authorities=_trusted(),
            transport=httpx.ASGITransport(app=app),
        )
        for quota, model in ((QUOTA, SERVED_MODEL), (OTHER_QUOTA, OTHER_MODEL)):
            await admin.register_resource(
                quota, total_units=10_000_000, resource_type="inference",
                attributes={"service": model}, pool_id="default",
            )
        yield app
    finally:
        unload_authority()


def _trusted() -> TrustedIdentitySet:
    return TrustedIdentitySet(identities=(AUTHORITY.identity,))


class CountingTransport(httpx.AsyncBaseTransport):
    """The authority over ASGI, counting the calls the gateway makes."""

    def __init__(self, app: Any) -> None:
        self._inner = httpx.ASGITransport(app=app)
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return await self._inner.handle_async_request(request)


def _tokens(transport: httpx.AsyncBaseTransport) -> TokensClient:
    return TokensClient(
        service_url=AUTHORITY_URL,
        http=httpx.AsyncClient(transport=transport, base_url=AUTHORITY_URL),
        signing=AuthoritySigning(
            authority_label=AUTHORITY_LABEL,
            signer=GATEWAY_SIGNER,
            expected_authorities=build_trusted_authorities([AUTHORITY.identity.model_dump(mode="json")]),
        ),
    )


async def _issue(
    app: Any, *, quantity: int, request_credits: int = 3,
    service: str = SERVED_MODEL, resource_id: str = QUOTA, negotiation_id: str = "neg-1",
):
    terms = accepted_terms(InferenceModelCard.model_validate(card(
        served_model_name=service, resource_id=resource_id, rate_card={"request_credits": request_credits},
    )))
    storefront = AuthorityClient(
        AUTHORITY_URL, label=INFERENCE_LABEL, transport=httpx.ASGITransport(app=app),
        signer=STOREFRONT_SIGNER, expected_authorities=_trusted(),
    )
    return await storefront.submit_issuance(issuance_request(
        INFERENCE_LABEL,
        negotiation_id=negotiation_id,
        owner=BUYER,
        service=service,
        resource_id=resource_id,
        quantity=quantity,
        key=KeyDisposition(mode="new"),
        accepted_terms=terms,
        terms_digest=accepted_terms_digest(terms),
        request_charge=request_credits,
    ))


async def _balance(app: Any, issued) -> int:
    verified = await _tokens(httpx.ASGITransport(app=app)).verify(
        key_id=issued.key_id, secret=issued.secret, service=SERVED_MODEL, resource_id=QUOTA,
    )
    return verified.balance


class Upstream:
    """A model server answering every completion, recording what reached it."""

    def __init__(self) -> None:
        self.forwarded: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.forwarded.append(request)
        return httpx.Response(200, json={"object": "chat.completion", "choices": [{"message": {"content": "hi"}}]})


def _gateway(
    authority_transport: httpx.AsyncBaseTransport, upstream: httpx.AsyncBaseTransport,
    storefront: Storefront | None = None, **card_fields: Any,
) -> GatewayService:
    storefront = storefront or Storefront([listing("lst-1", **card_fields)])
    return create_app(
        settings(listing_retry_seconds=0.01),
        GateConfig(service_url=AUTHORITY_URL, authority_label=AUTHORITY_LABEL),
        storefront_transport=httpx.MockTransport(storefront.handle),
        authority=_tokens(authority_transport),
        http=httpx.AsyncClient(transport=upstream),
    )


@contextlib.asynccontextmanager
async def _running(service: GatewayService) -> AsyncIterator[httpx.AsyncClient]:
    inbox: asyncio.Queue[dict] = asyncio.Queue()
    outbox: asyncio.Queue[dict] = asyncio.Queue()
    lifespan = asyncio.ensure_future(service({"type": "lifespan"}, inbox.get, outbox.put))
    await inbox.put({"type": "lifespan.startup"})
    assert (await outbox.get())["type"] == "lifespan.startup.complete"
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service), base_url="http://gateway") as client:
            await asyncio.wait_for(service.loaded.wait(), 5)
            yield client
    finally:
        await inbox.put({"type": "lifespan.shutdown"})
        assert (await outbox.get())["type"] == "lifespan.shutdown.complete"
        await lifespan


def _completion(secret: str, model: str = SERVED_MODEL) -> dict[str, Any]:
    return {
        "json": {"model": model, "messages": [{"role": "user", "content": "hello"}]},
        "headers": {"authorization": f"Bearer {secret}"},
    }


async def test_an_admitted_request_is_charged_the_key_s_pinned_charge(authority):
    issued = await _issue(authority, quantity=100)
    upstream = Upstream()

    async with _running(_gateway(httpx.ASGITransport(app=authority), httpx.MockTransport(upstream.handle))) as client:
        response = await client.post("/v1/chat/completions", **_completion(issued.secret))

    assert response.status_code == 200
    assert len(upstream.forwarded) == 1
    assert await _balance(authority, issued) == 97


async def test_a_key_bought_for_another_offering_is_403_and_untouched(authority):
    issued = await _issue(authority, quantity=100, service=OTHER_MODEL, resource_id=OTHER_QUOTA)
    upstream = Upstream()

    async with _running(_gateway(httpx.ASGITransport(app=authority), httpx.MockTransport(upstream.handle))) as client:
        response = await client.post("/v1/chat/completions", **_completion(issued.secret))

    assert response.status_code == 403
    assert upstream.forwarded == []
    other = await _tokens(httpx.ASGITransport(app=authority)).verify(
        key_id=issued.key_id, secret=issued.secret, service=OTHER_MODEL, resource_id=OTHER_QUOTA,
    )
    assert other.balance == 100


async def test_an_unlisted_model_is_404_with_no_authority_call(authority):
    issued = await _issue(authority, quantity=100)
    counting = CountingTransport(authority)
    upstream = Upstream()

    async with _running(_gateway(counting, httpx.MockTransport(upstream.handle))) as client:
        response = await client.post("/v1/chat/completions", **_completion(issued.secret, model=OTHER_MODEL))

    assert response.status_code == 404
    assert (counting.calls, upstream.forwarded) == (0, [])


async def test_an_exhausted_key_is_402_pointing_at_the_storefront_and_registry(authority):
    issued = await _issue(authority, quantity=3)
    upstream = Upstream()

    async with _running(_gateway(httpx.ASGITransport(app=authority), httpx.MockTransport(upstream.handle))) as client:
        assert (await client.post("/v1/chat/completions", **_completion(issued.secret))).status_code == 200
        response = await client.post("/v1/chat/completions", **_completion(issued.secret))

    assert response.status_code == 402
    assert response.json()["purchase"] == {
        "service_name": SERVED_MODEL, "listing_id": "lst-1",
        "storefront_url": STOREFRONT_URL, "registry_url": REGISTRY_URL,
    }
    assert len(upstream.forwarded) == 1


async def test_a_republished_default_charge_leaves_an_existing_key_s_charge(authority):
    issued = await _issue(authority, quantity=100, request_credits=3)
    upstream = Upstream()
    gateway = _gateway(
        httpx.ASGITransport(app=authority), httpx.MockTransport(upstream.handle),
        rate_card={"request_credits": 5},
    )

    async with _running(gateway) as client:
        response = await client.post("/v1/chat/completions", **_completion(issued.secret))

    assert response.status_code == 200
    assert await _balance(authority, issued) == 97


async def test_the_gateway_is_not_ready_until_its_listing_is_published(authority):
    storefront = Storefront([])
    gateway = _gateway(httpx.ASGITransport(app=authority), httpx.MockTransport(Upstream().handle), storefront)
    inbox: asyncio.Queue[dict] = asyncio.Queue()
    outbox: asyncio.Queue[dict] = asyncio.Queue()
    lifespan = asyncio.ensure_future(gateway({"type": "lifespan"}, inbox.get, outbox.put))
    await inbox.put({"type": "lifespan.startup"})
    await outbox.get()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url="http://gateway") as client:
        await asyncio.wait_for(gateway.refused.wait(), 5)
        waiting = await client.get("/health")
        storefront.listings.append(listing("lst-1"))
        await asyncio.wait_for(gateway.loaded.wait(), 5)
        ready = await client.get("/health")
    await inbox.put({"type": "lifespan.shutdown"})
    await outbox.get()
    await lifespan

    assert waiting.status_code == 503
    assert "0 open listings" in waiting.json()["reason"]
    assert ready.status_code == 200


class ControlledStream:
    """A model server that streams one event, then holds the last until released."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.sent_last = False

    async def events(self) -> AsyncIterator[bytes]:
        yield b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        await self.release.wait()
        self.sent_last = True
        yield b"data: [DONE]\n\n"

    def handle(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=self.events())


@contextlib.asynccontextmanager
async def _served(app: Any) -> AsyncIterator[str]:
    """``app`` on a socket in this event loop; ``ASGITransport`` collects a body before returning it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    serving = asyncio.ensure_future(server.serve(sockets=[sock]))
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        await serving
        sock.close()


async def test_a_streamed_completion_reaches_the_buyer_before_the_model_finishes(authority):
    issued = await _issue(authority, quantity=100)
    upstream = ControlledStream()
    gateway = _gateway(httpx.ASGITransport(app=authority), httpx.MockTransport(upstream.handle))

    async with _served(gateway) as base_url:
        await asyncio.wait_for(gateway.loaded.wait(), 5)
        async with httpx.AsyncClient(base_url=base_url, timeout=5) as client, client.stream(
            "POST", "/v1/chat/completions",
            json={"model": SERVED_MODEL, "stream": True, "messages": []},
            headers={"authorization": f"Bearer {issued.secret}"},
        ) as response:
            lines = response.aiter_lines()
            first = await anext(lines)
            finished_early = upstream.sent_last
            upstream.release.set()
            rest = [line async for line in lines if line]

    assert "first" in first
    assert not finished_early
    assert rest == ["data: [DONE]"]
    assert await _balance(authority, issued) == 97
