"""A configuration the storefront cannot honour fails startup, naming the problem."""

from __future__ import annotations

from typing import Any

import pytest

from inference_storefront import container, server
from inference_storefront.startup_refusal import (
    AUTHORITY_HEADING,
    MECHANISM_HEADING,
    WALLET_HEADING,
    StorefrontStartupError,
)
from inference_storefront.utils import config as storefront_config
from tests.integration.conftest import (
    AUTHORITY_URL,
    SELLER_WALLET,
    SELLER_WALLET_KEY,
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
    with replaced(
        settlement=settlement("alkahest.v1", "arkhai.payments.v1"),
        wallet={"address": "0x" + "33" * 20, "private_key": SELLER_WALLET_KEY},
    ):
        refusal = await _refused(storefront)

    assert MECHANISM_HEADING in refusal
    assert AUTHORITY_HEADING in refusal
    assert WALLET_HEADING in refusal


async def test_a_wallet_address_its_key_does_not_derive_fails_startup(storefront):
    # A development address that is not Anvil account 0's.
    with replaced(wallet={"address": "0x" + "33" * 20, "private_key": SELLER_WALLET_KEY}):
        refusal = await _refused(storefront)

    assert WALLET_HEADING in refusal
    assert "mismatch" in refusal


async def test_the_chain_clients_and_the_release_recipient_share_one_wallet(storefront, monkeypatch):
    signing_keys: list[str] = []

    def chain_clients(private_key: str) -> dict[str, Any]:
        signing_keys.append(private_key)
        return {}

    async def no_startup_tasks(*, domain: Any) -> None:
        return None

    monkeypatch.setattr(server, "_build_alkahest_clients", chain_clients)
    monkeypatch.setattr(server, "_startup_tasks", no_startup_tasks)
    served = app()
    async with served.router.lifespan_context(served):
        assert signing_keys == [SELLER_WALLET_KEY]
        assert container.resolved_seller_wallet == SELLER_WALLET
        assert container.ALKAHEST_STAGE._seller_wallet() == SELLER_WALLET
        # A later change to the settings does not move the release recipient.
        storefront_config.settings.set("wallet.address", "0x" + "33" * 20)
        assert container.ALKAHEST_STAGE._seller_wallet() == SELLER_WALLET

    assert container.resolved_seller_wallet is None
