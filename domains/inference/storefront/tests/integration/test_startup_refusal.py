"""A configuration the storefront cannot honour fails startup, naming the problem."""

from __future__ import annotations

import pytest

from inference_storefront import container
from inference_storefront.startup_refusal import (
    AUTHORITY_HEADING,
    MECHANISM_HEADING,
    StorefrontStartupError,
)
from tests.integration.conftest import (
    AUTHORITY_URL,
    app,
    replaced,
    settlement,
)


async def _refused(storefront) -> str:
    served = app()
    with pytest.raises(StorefrontStartupError) as refused:
        async with served.router.lifespan_context(served):
            pass
    # Refused before the storefront opened its database.
    assert container._sqlite_client is None
    assert not storefront.exists()
    return str(refused.value)


async def test_a_second_mechanism_fails_startup_before_anything_is_served(storefront):
    with replaced(settlement=settlement("alkahest.v1", "arkhai.payments.v1")):
        refusal = await _refused(storefront)

    assert MECHANISM_HEADING in refusal
    assert "'arkhai.payments.v1'" in refusal


async def test_a_storefront_without_its_signing_credential_fails_startup(storefront, monkeypatch):
    monkeypatch.delenv("ARKHAI_IDENTITY_CREDENTIAL")

    refusal = await _refused(storefront)

    assert AUTHORITY_HEADING in refusal
    assert "ARKHAI_IDENTITY_CREDENTIAL" in refusal


async def test_a_storefront_without_the_authority_trust_set_fails_startup(storefront):
    with replaced(credits={"service_url": AUTHORITY_URL}):
        refusal = await _refused(storefront)

    assert AUTHORITY_HEADING in refusal
    assert "[credits.expected_authorities]" in refusal


async def test_every_problem_is_reported_together(storefront, monkeypatch):
    monkeypatch.delenv("ARKHAI_IDENTITY_CREDENTIAL")
    with replaced(settlement=settlement("alkahest.v1", "arkhai.payments.v1")):
        refusal = await _refused(storefront)

    assert MECHANISM_HEADING in refusal
    assert AUTHORITY_HEADING in refusal
