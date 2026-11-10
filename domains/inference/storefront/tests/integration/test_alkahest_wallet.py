"""The seller is one account: the wallet's address, else the one its key signs as."""

from __future__ import annotations

import pytest
from storefront_client import StorefrontClientError

from tests.cards import model_card
from tests.integration.conftest import (
    ESCROW,
    SELLER_WALLET,
    SELLER_WALLET_KEY,
    replaced,
    running,
)


def _publish_request() -> dict:
    return {
        "resource_id": "svc-quota",
        "accepted_escrows": [dict(ESCROW)],
        "model_card": model_card(),
    }


async def test_a_seller_stating_only_a_key_publishes_the_keys_account_as_recipient(
    storefront, quota_site, registries, monkeypatch
):
    with replaced(wallet={"private_key": SELLER_WALLET_KEY}):
        async with running(monkeypatch) as clients:
            created = await clients.seller.publish_from_quota(_publish_request())
            listing = await clients.public.get_listing(created.listing_id)

    assert created.status == "created"
    assert [demand["demand_data"] for demand in listing.extra["demands"]] == [
        {"recipient": SELLER_WALLET.lower()}
    ]


async def test_an_address_naming_another_account_starts_and_publishes_no_alkahest_option(
    storefront, quota_site, registries, monkeypatch
):
    # A development address that is not the key's account.
    with replaced(wallet={"address": "0x" + "33" * 20, "private_key": SELLER_WALLET_KEY}):
        async with running(monkeypatch) as clients:
            with pytest.raises(
                StorefrontClientError, match="alkahest.wallet_address_mismatch"
            ) as refused:
                await clients.seller.publish_from_quota(_publish_request())

    assert refused.value.status_code == 400
    assert registries.published == []
