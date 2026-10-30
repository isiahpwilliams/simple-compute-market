"""A delivery's public result carries the rate card accepted, not the one republished since."""

from __future__ import annotations

from arkhai_inference.listings import InferenceRateCard
from arkhai_inference.schema import InferenceMaterialization

from inference_storefront.container import storefront_sqlite_client
from inference_storefront.services.fulfillment_service import fulfill_inference_obligation
from tests.cards import bound_card
from tests.integration.issuance_authority import ESCROW_UID, ScriptedAuthority, evidence


async def test_the_public_result_carries_the_card_in_force_at_acceptance(tmp_path):
    accepted = bound_card()
    republished = bound_card()
    republished["rate_card"] = {**republished["rate_card"], "request_credits": 9}
    authority = ScriptedAuthority()

    # The seller has since republished at another rate; the evidence carries
    # the listing recorded at acceptance.
    result = await fulfill_inference_obligation(
        evidence=evidence(accepted),
        db=storefront_sqlite_client(str(tmp_path / "storefront.db")),
        credits_client=authority.client(),
    )

    extension = result["public_extension"]
    materialization = InferenceMaterialization.model_validate(extension["materialization"])
    assert materialization.rate_card.request_credits == 3
    assert materialization.rate_card != InferenceRateCard.model_validate(republished["rate_card"])
    assert (materialization.mechanism, materialization.escrow_uid) == ("alkahest.v1", ESCROW_UID)
    assert materialization.fulfillment_id == result["fulfillment_uid"]
    assert materialization.key_id == "ik_new"
    assert "s3cret" not in str(extension)
    assert authority.requests[0]["request_charge"] == 3
