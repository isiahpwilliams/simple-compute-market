"""The storefront starts, with its loops, while its inference authority does not answer."""

from __future__ import annotations

import httpx
from storefront_client import StorefrontClient

from inference_storefront import container
from tests.integration.conftest import app


async def test_startup_does_not_wait_for_the_authority(storefront):
    # Nothing answers at the configured authority or site URL, and nothing here
    # stubs the startup tasks.
    served = app()
    async with served.router.lifespan_context(served):
        loops = container.resolved_loop_controller
        async with StorefrontClient(
            "http://seller", transport=httpx.ASGITransport(app=served)
        ) as public:
            health = await public.get_health()
        started = set(loops.snapshot())

    assert health.checks["database"] == "ok"
    assert "alkahest_chain_probe" in started
