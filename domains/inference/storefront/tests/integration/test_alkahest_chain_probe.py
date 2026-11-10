"""The storefront reaches its chains through the probe its lifecycle loop steps."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from market_identity import TrustedIdentitySet
from storefront_client import StorefrontClient

from inference_storefront import container, server
from tests.integration.conftest import (
    ADMIN_SIGNER,
    ANVIL,
    SELLER_SIGNER,
    app,
    deployed_chain,
    replaced,
    settlement,
)


@asynccontextmanager
async def _started(monkeypatch, seams: server.InferenceCompositionSeams) -> AsyncIterator[tuple[StorefrontClient, StorefrontClient]]:
    """The started storefront, no loop running, with a public and an admin client."""

    async def no_startup_tasks(*, domain: Any) -> None:
        return None

    monkeypatch.setattr(server, "_startup_tasks", no_startup_tasks)
    served = app(seams)
    async with served.router.lifespan_context(served):
        transport = httpx.ASGITransport(app=served)
        async with StorefrontClient("http://seller", transport=transport) as public, StorefrontClient(
            "http://seller",
            signer=ADMIN_SIGNER,
            caller_role="admin",
            expected_publishers=TrustedIdentitySet(identities=(SELLER_SIGNER.identity,)),
            transport=transport,
        ) as admin:
            yield public, admin


def _alkahest_status(status: Any) -> dict[str, Any]:
    (alkahest,) = [item for item in status.settlement if item["mechanism"] == "alkahest.v1"]
    return alkahest


async def test_the_composition_and_the_loop_share_one_probe_over_one_client_map(storefront, monkeypatch):
    answering: set[str] = set()

    def rpc(rpc_url: str, method: str, params: Any, timeout: float) -> str:
        if "anvil" not in answering:
            raise ConnectionRefusedError("connection refused")
        return deployed_chain(rpc_url, method, params, timeout)

    def constructor(_policy: Any) -> Any:
        def construct(chain_name: str) -> object:
            if chain_name not in answering:
                raise ConnectionRefusedError("websocket upgrade refused")
            return f"client:{chain_name}"

        return construct

    seams = server.InferenceCompositionSeams(alkahest_client_constructor=constructor, alkahest_json_rpc=rpc)
    async with _started(monkeypatch, seams) as (_public, admin):
        await admin.admin_run_lifecycle_cycle("alkahest-chain-probe")
        refused = _alkahest_status(await admin.get_system_status())
        answering.add("anvil")
        await admin.admin_run_lifecycle_cycle("alkahest-chain-probe")
        reached = _alkahest_status(await admin.get_system_status())
        probe = container.resolved_alkahest_chain_probe
        composition = container.resolved_settlement_composition

    assert [blocker["code"] for blocker in refused["blockers"]] == ["alkahest.chain_unreachable"]
    assert reached["ready"] is True
    assert composition.mechanism_resources["clients"] is probe.clients
    assert probe.clients == {ANVIL.name: "client:anvil"}


async def test_startup_does_not_wait_on_a_chain_whose_client_never_finishes_building(storefront, monkeypatch):
    never_upgraded = threading.Event()
    constructed_on: list[str] = []

    def constructor(_policy: Any) -> Any:
        def construct(chain_name: str) -> object:
            constructed_on.append(threading.current_thread().name)
            # Only the probe's own construction thread is held: one anywhere
            # else, as startup's would be, fails at once, so the assertion below
            # names it rather than the test hanging.
            if threading.current_thread().name.startswith("alkahest-client-"):
                never_upgraded.wait()
            raise ConnectionError("websocket closed")

        return construct

    seams = server.InferenceCompositionSeams(
        alkahest_client_constructor=constructor, alkahest_json_rpc=deployed_chain
    )
    bounded = settlement()
    bounded["alkahest"]["rpc_timeout_seconds"] = 0.2
    try:
        with replaced(settlement=bounded):
            async with _started(monkeypatch, seams) as (public, admin):
                health = await public.get_health()
                await asyncio.wait_for(admin.admin_run_lifecycle_cycle("alkahest-chain-probe"), timeout=5)
                status = _alkahest_status(await admin.get_system_status())
    finally:
        never_upgraded.set()

    assert health.checks["database"] == "ok"
    assert constructed_on and all(name.startswith("alkahest-client-") for name in constructed_on), constructed_on
    assert status["ready"] is False
    assert [(b["code"], b["kind"]) for b in status["blockers"]] == [
        ("alkahest.chain_unreachable", "reachability")
    ]
