"""The delivery's public materialization: the accepted card and the rate card it pins."""

from __future__ import annotations

import pytest
from arkhai_api.issuance import IssuanceResult
from arkhai_api_selling.contributions import DeliveryContext
from arkhai_inference.listings import InferenceModelCard
from arkhai_inference.schema import InferenceMaterialization
from market_identity import Ed25519Signer
from pydantic import ValidationError

from inference_storefront.materialization import public_result_extension
from tests.cards import bound_card

ESCROW_UID = "0x" + "ab" * 32


def _result(**fields) -> IssuanceResult:
    values = {
        "schema": "arkhai.inference.issuance-result.v1",
        "negotiation_id": "neg-1",
        "fulfillment_id": "inference-fulfillment.v1:abc",
        "grant_id": "inference-fulfillment.v1:abc",
        "owner": Ed25519Signer(b"\x11" * 32).identity,
        "service": "stub-instruct",
        "resource_id": "svc-quota",
        "quantity": 40,
        "key_mode": "new",
        "key_id": "ik_1",
        "balance": 40,
        "request_digest": "sha256:" + "0" * 64,
        "committed_at_unix": 1,
    }
    values.update(fields)
    return IssuanceResult.model_validate(values)


def test_the_extension_carries_the_contracts_materialization_of_the_accepted_card() -> None:
    card = bound_card()

    extension = public_result_extension(
        card, _result(), DeliveryContext("alkahest.v1", ESCROW_UID)
    )

    assert set(extension) == {"materialization"}
    materialization = InferenceMaterialization.model_validate(extension["materialization"])
    assert materialization.listing_resource == InferenceModelCard.model_validate(card)
    assert materialization.rate_card == materialization.listing_resource.rate_card
    assert (materialization.quantity, materialization.key_mode, materialization.key_id) == (
        40,
        "new",
        "ik_1",
    )
    assert materialization.fulfillment_id == "inference-fulfillment.v1:abc"
    assert (materialization.mechanism, materialization.escrow_uid) == ("alkahest.v1", ESCROW_UID)


def test_a_rate_card_other_than_the_listings_is_refused() -> None:
    extension = public_result_extension(
        bound_card(), _result(), DeliveryContext("alkahest.v1", ESCROW_UID)
    )
    tampered = dict(extension["materialization"])
    tampered["rate_card"] = {**tampered["rate_card"], "request_credits": "1"}

    with pytest.raises(ValidationError, match="rate_card must equal"):
        InferenceMaterialization.model_validate(tampered)


def test_an_existing_key_top_up_names_the_key() -> None:
    extension = public_result_extension(
        bound_card(),
        _result(key_mode="existing", key_id="ik_existing"),
        DeliveryContext("alkahest.v1", ESCROW_UID),
    )

    assert extension["materialization"]["key_mode"] == "existing"
    assert extension["materialization"]["key_id"] == "ik_existing"
