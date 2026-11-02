"""The issuance request the storefront sends carries the accepted terms, digest, charge, and label."""

from __future__ import annotations

from arkhai_api.issuance import accepted_terms_digest, issuance_request_digest
from arkhai_inference.label import INFERENCE_LABEL
from arkhai_inference.listings import InferenceModelCard, accepted_terms

from inference_storefront.container import storefront_sqlite_client
from inference_storefront.services.fulfillment_service import fulfill_inference_obligation
from tests.cards import bound_card
from tests.integration.issuance_authority import IssuanceRequest, ScriptedAuthority, evidence


async def test_the_request_pins_the_accepted_card_under_the_inference_label(tmp_path):
    card = bound_card()
    authority = ScriptedAuthority()

    result = await fulfill_inference_obligation(
        evidence=evidence(card),
        db=storefront_sqlite_client(str(tmp_path / "storefront.db")),
        credits_client=authority.client(),
    )

    assert result["status"] == "fulfilled"
    (body,) = authority.requests
    terms = accepted_terms(InferenceModelCard.model_validate(card))
    assert body["schema"] == INFERENCE_LABEL.issuance_request_schema
    assert body["fulfillment_id"].startswith("inference-fulfillment.v1")
    assert (body["service"], body["resource_id"]) == ("stub-instruct", "svc-quota")
    assert body["accepted_terms"] == terms
    assert body["terms_digest"] == accepted_terms_digest(terms)
    assert body["request_charge"] == 3
    request = IssuanceRequest.model_validate(body)
    assert body["request_digest"] == issuance_request_digest(INFERENCE_LABEL, request)
