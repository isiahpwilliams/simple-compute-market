"""The gateway refuses bad configuration at startup and retries only an unavailable listing."""

from __future__ import annotations

import asyncio
import json
from base64 import urlsafe_b64encode
from pathlib import Path

import httpx
import pytest
from arkhai_api_gate import GateConfig, TokensClient
from market_identity import Ed25519Signer

from inference_gateway_service.config import AUTHORITY_LABEL
from inference_gateway_service.main import GatewayService, create_app
from tests.cards import Storefront, listing, settings

# Deterministic development seeds for these tests only; never used on any network.
GATEWAY_SEED = b"inference-gateway-seed-32-bytes!"
AUTHORITY = Ed25519Signer(b"inference-authority-seed-32byte!")


def _gate(**fields: str) -> GateConfig:
    return GateConfig(service_url="http://authority.test", authority_label=AUTHORITY_LABEL, **fields)


def _signing_gate() -> GateConfig:
    return _gate(
        identity_credential=urlsafe_b64encode(GATEWAY_SEED).rstrip(b"=").decode(),
        authority_principals=json.dumps([AUTHORITY.identity.model_dump(mode="json")]),
    )


def _authority() -> TokensClient:
    return TokensClient(service_url="http://authority.test")


def test_a_malformed_identity_credential_stops_startup():
    with pytest.raises(Exception, match="(?i)credential|signer|base64|key"):
        create_app(settings(), _gate(identity_credential="not-a-credential"))


def test_a_bad_model_server_url_stops_startup():
    with pytest.raises(ValueError):
        create_app(settings(upstream_base_url="ftp://model.test/v1"), _gate(), authority=_authority())


def test_an_unreadable_upstream_credential_stops_startup(tmp_path: Path):
    with pytest.raises(ValueError, match="upstream credential"):
        create_app(
            settings(upstream_credential_file=tmp_path / "missing"), _gate(), authority=_authority(),
        )


async def _lifespan(service: GatewayService):
    inbox: asyncio.Queue[dict] = asyncio.Queue()
    outbox: asyncio.Queue[dict] = asyncio.Queue()
    task = asyncio.ensure_future(service({"type": "lifespan"}, inbox.get, outbox.put))
    await inbox.put({"type": "lifespan.startup"})
    assert (await outbox.get())["type"] == "lifespan.startup.complete"
    return inbox, outbox, task


async def _shutdown(inbox, outbox, task) -> None:
    await inbox.put({"type": "lifespan.shutdown"})
    assert (await outbox.get())["type"] == "lifespan.shutdown.complete"
    await task


async def test_an_error_other_than_an_unavailable_listing_is_not_retried():
    attempts: list[None] = []

    async def load():
        attempts.append(None)
        raise RuntimeError("not a listing problem")

    service = GatewayService(load, retry_seconds=0)
    lifespan = await _lifespan(service)
    await asyncio.wait_for(service.refused.wait(), 5)
    await asyncio.wait_for(service._loader, 5)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service), base_url="http://gateway") as client:
        health = await client.get("/health")
    await _shutdown(*lifespan)

    assert attempts == [None]
    assert health.status_code == 503
    assert health.json()["reason"].startswith("failed:")


async def test_every_load_reuses_the_one_authority_client(monkeypatch):
    def no_second_client(*args, **kwargs):
        raise AssertionError("the gateway library built its own authority client")

    monkeypatch.setattr("arkhai_api_gateway.app.TokensClient", no_second_client)
    storefront = Storefront([])
    service = create_app(
        settings(listing_retry_seconds=0), _signing_gate(),
        storefront_transport=httpx.MockTransport(storefront.handle),
    )
    lifespan = await _lifespan(service)
    await asyncio.wait_for(service.refused.wait(), 5)
    storefront.listings.append(listing("lst-1"))
    await asyncio.wait_for(service.loaded.wait(), 5)
    await _shutdown(*lifespan)

    assert len(storefront.pages) >= 2
