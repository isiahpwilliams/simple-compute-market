"""A per-token rate card is refused at publication, naming the field, and nothing is published."""

from __future__ import annotations

import pytest
from storefront_client.client import StorefrontClientError

from tests.cards import ASSET, model_card
from tests.integration.conftest import ESCROW, running


async def test_a_per_token_rate_card_is_refused_naming_the_field(
    storefront, quota_site, registries, monkeypatch
):
    card = model_card(
        rate_card={
            "asset": ASSET,
            "prompt_credits_per_million": 5,
            "completion_credits_per_million": 0,
            "request_credits": 1,
        }
    )
    async with running(monkeypatch) as clients:
        with pytest.raises(StorefrontClientError) as refused:
            await clients.seller.publish_from_quota(
                {"resource_id": "svc-quota", "accepted_escrows": [dict(ESCROW)], "model_card": card}
            )
        listings = await clients.public.list_listings()

    assert refused.value.status_code == 400
    assert "rate_card.prompt_credits_per_million" in str(refused.value)
    assert listings.listings == []
    assert registries.published == []
