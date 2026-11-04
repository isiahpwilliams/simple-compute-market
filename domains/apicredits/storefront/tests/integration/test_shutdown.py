"""The storefront's lifespan ends only once its background loops have."""

from __future__ import annotations

import asyncio
from typing import Any

from apicredits_storefront import container, server
from tests.integration.test_alkahest_release_conditions import (
    _app,
    _replaced,
    _settlement,
    storefront,  # noqa: F401 - the configuration this test starts from
)


async def test_shutdown_returns_once_every_background_loop_has_ended(storefront, monkeypatch):  # noqa: F811
    started = asyncio.Event()
    tasks: dict[str, asyncio.Task[Any]] = {}

    async def step() -> dict[str, Any]:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            # A cancelled loop unwinds across an await before it ends.
            await asyncio.sleep(0)
        return {}

    async def start_one_loop(*, domain: Any) -> None:
        loops = container.resolved_loop_controller
        loops.register_loop("held", step=step, interval_seconds=60)
        tasks.update(loops.start_loops())

    monkeypatch.setattr(server, "_startup_tasks", start_one_loop)
    served = _app()
    with _replaced(settlement=_settlement()):
        async with served.router.lifespan_context(served):
            await asyncio.wait_for(started.wait(), 5)

    assert tasks and all(task.done() for task in tasks.values())
