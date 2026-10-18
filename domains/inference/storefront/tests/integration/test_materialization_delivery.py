"""Delivery records the materialization and hands it to the buyer beside the key.

The settled deal and the coordinator come from the copied fulfillment suite, which
keeps them beside the tests that first used them.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from arkhai_inference.settlement.credits_client import CreditsServiceClient

from inference_storefront.domain_runtime import get_market_domain_contract
from inference_storefront.listing_binding import inference_registration
from inference_storefront.settlement_stages import project_progress
from core_storefront.domain_registry import StorefrontDomainRegistry
from tests.integration.credit_negotiation import model_card
from tests.unit.test_settlement_fulfillment import (  # noqa: F401 - the settled_db fixture
    _BUYER_PRINCIPAL,
    _build_settlement_composition,
    _issuance_result,
    _settlement_request,
    settled_db,
)


async def test_the_delivered_materialization_pins_the_accepted_card(settled_db, monkeypatch):
    db, neg_id = settled_db
    from inference_storefront import settlement_stages

    # Repriced after acceptance: the delivered card must be the accepted one.
    await db.update_listing(listing_id="L-tok", listing_resource=model_card(request_credits=5))

    async def verify(**_kwargs):
        return 0

    async def issue(self, request):
        return _issuance_result(request)

    async def attest(_payload, _escrow_uid):
        return "0xfulfill"

    monkeypatch.setattr(settlement_stages, "verify_escrow_for_settlement", verify)
    monkeypatch.setattr(CreditsServiceClient, "submit_credit_issuance", issue)
    client = SimpleNamespace(string_obligation=SimpleNamespace(do_obligation=attest))
    completed = asyncio.Event()
    _runtime, _worker, coordinator = _build_settlement_composition(db, on_outcome=completed.set)

    await coordinator.start(
        escrow_uid="0xdeal", negotiation_id=neg_id, mechanism_client=client, chain_name="anvil",
        request=_settlement_request(neg_id),
    )
    await asyncio.wait_for(completed.wait(), timeout=5)

    progress = await db.load_issuance_progress(reference="0xdeal")
    materialization = progress["public_result"]["materialization"]
    assert materialization["rate_card"]["request_credits"] == 1
    assert (materialization["escrow_uid"], materialization["key_id"], materialization["quantity"]) == ("0xdeal", "ik_new", 3)
    assert "s3cret" not in json.dumps(materialization)

    projection = await project_progress(db, progress, owner=_BUYER_PRINCIPAL)
    assert projection["materialization"] == materialization
    assert "materialization" not in projection["tenant_credentials"]

    recorded = await db.load_domain_artifact(
        negotiation_id=neg_id,
        artifact_slot="materialization",
        registry=StorefrontDomainRegistry((inference_registration(get_market_domain_contract()),)),
    )
    assert recorded.model_dump(mode="json", exclude_none=True) == materialization
