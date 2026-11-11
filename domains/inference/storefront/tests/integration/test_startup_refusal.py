"""A configuration the storefront cannot honour fails startup, naming the problem."""

from __future__ import annotations

import pytest

from inference_storefront import container
from inference_storefront.retired_settings import RETIRED_SETTINGS_HEADING
from inference_storefront.startup_refusal import (
    AUTHORITY_HEADING,
    CREDITS_HEADING,
    MECHANISM_HEADING,
    StorefrontStartupError,
)
from tests.integration.conftest import (
    AUTHORITY_SIGNER,
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


async def test_an_unset_authority_url_fails_startup(storefront):
    # The signer, trust set, and capacity are all valid; only the URL is empty.
    with replaced(
        credits={
            "service_url": "",
            "expected_authorities": {
                "identities": [AUTHORITY_SIGNER.identity.model_dump(mode="json")]
            },
        }
    ):
        refusal = await _refused(storefront)

    assert refusal == f"{CREDITS_HEADING}: [credits].service_url is not configured"


@pytest.mark.parametrize(
    "key,value",
    [
        ("fail_on_unreachable", True),
        ("fail_on_unreachable", False),
        ("preflight_timeout", 30),
    ],
)
async def test_a_removed_preflight_setting_fails_startup_naming_it(storefront, key, value):
    with replaced(
        credits={
            "service_url": AUTHORITY_URL,
            key: value,
            "expected_authorities": {
                "identities": [AUTHORITY_SIGNER.identity.model_dump(mode="json")]
            },
        }
    ):
        refusal = await _refused(storefront)

    assert refusal.startswith(f"{RETIRED_SETTINGS_HEADING}: credits.{key} was removed: ")
    assert "starts without waiting for its inference authority" in refusal
