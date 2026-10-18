"""The rate card is pinned at acceptance and the materialization is recorded once."""

from __future__ import annotations

import pytest
from arkhai_inference.schema import InferenceMaterialization

from inference_storefront.domain_runtime import get_market_domain_contract
from inference_storefront.materialization import (
    PinnedRateCardConflict,
    pinned_rate_card,
    store_materialization,
)
from inference_storefront.negotiation_runtime import build_inference_negotiation_runtime
from tests.integration.credit_negotiation import (
    BUYER_PRINCIPAL,
    SELLER_PRINCIPAL,
    model_card,
    proposal,
    terms,
)

_DOMAIN = get_market_domain_contract()
_FULFILLMENT_ID = "inference-fulfillment.v1:" + "0" * 64


async def _accept(db) -> str:
    response = await build_inference_negotiation_runtime(_DOMAIN).start(
        repository=db,
        listing_id="L-tok",
        buyer_principal=BUYER_PRINCIPAL,
        seller_principal=SELLER_PRINCIPAL,
        proposal=proposal(3),
        terms=terms(3),
        seller_agent_url="http://seller:8002",
        buyer_agent_url="http://buyer:9000",
        actor_principal=BUYER_PRINCIPAL,
    )
    assert response["action"] == "accept"
    return response["negotiation_id"]


def _materialization(rate_card, **overrides) -> InferenceMaterialization:
    fields = dict(
        escrow_uid="escrow-1",
        quantity=3,
        key_id="ik_1",
        rate_card=rate_card,
        fulfillment_id=_FULFILLMENT_ID,
        mechanism="alkahest.v1",
    )
    fields.update(overrides)
    return InferenceMaterialization(**fields)


async def test_republishing_after_acceptance_does_not_change_the_pinned_card(
    db, fake_capacity, key_records
):
    negotiation_id = await _accept(db)
    await db.update_listing(listing_id="L-tok", listing_resource=model_card(request_credits=5))

    pinned = await pinned_rate_card(db, negotiation_id)
    assert pinned.request_credits == 1

    stored = await store_materialization(
        db, domain=_DOMAIN, negotiation_id=negotiation_id, materialization=_materialization(pinned)
    )
    assert stored.rate_card.request_credits == 1


async def test_the_materialization_is_recorded_once(db, fake_capacity, key_records):
    negotiation_id = await _accept(db)
    pinned = await pinned_rate_card(db, negotiation_id)
    first = _materialization(pinned)
    await store_materialization(db, domain=_DOMAIN, negotiation_id=negotiation_id, materialization=first)

    assert await store_materialization(
        db, domain=_DOMAIN, negotiation_id=negotiation_id, materialization=_materialization(pinned)
    ) == first
    with pytest.raises(PinnedRateCardConflict):
        await store_materialization(
            db, domain=_DOMAIN, negotiation_id=negotiation_id,
            materialization=_materialization(pinned, quantity=4),
        )


async def test_a_negotiation_that_pinned_no_card_cannot_materialize(db):
    with pytest.raises(RuntimeError, match="pinned no rate card"):
        await pinned_rate_card(db, "neg-missing")
