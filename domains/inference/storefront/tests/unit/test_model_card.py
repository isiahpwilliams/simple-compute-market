"""The publication mapping: an operator's card bound to the quota resource it is created over."""

from __future__ import annotations

import pytest
from arkhai_api_selling.contributions import QuotaSource
from arkhai_inference.listings import InferenceModelCard, derive_model_id

from inference_storefront.model_card import PublishFromQuotaRequest, publication_mapping
from tests.cards import model_card

QUOTA = QuotaSource(site_id="tokens", resource_id="svc-quota", offering_mode="inference")


def test_the_quota_fills_the_resource_site_and_mode() -> None:
    resource = publication_mapping({"model_card": model_card()}, QUOTA)

    card = InferenceModelCard.model_validate(resource)
    assert (card.resource_id, card.capacity_site_id, card.offering_mode) == (
        "svc-quota",
        "tokens",
        "inference",
    )
    assert card.served_model_name == "stub-instruct"


def test_a_card_naming_another_resource_is_bound_to_its_quota() -> None:
    resource = publication_mapping(
        {"model_card": model_card(resource_id="other-quota", capacity_site_id="elsewhere")}, QUOTA
    )

    assert (resource["resource_id"], resource["capacity_site_id"]) == ("svc-quota", "tokens")


def test_model_id_is_derived_from_owner_and_name() -> None:
    card = model_card(owner="Arkhai", name="Stub-Instruct")
    del card["model_id"]

    resource = publication_mapping({"model_card": card}, QUOTA)

    assert resource["model_id"] == derive_model_id("Arkhai", "Stub-Instruct")
    assert "owner" not in resource and "name" not in resource


def test_a_card_with_no_model_identity_is_refused() -> None:
    card = model_card()
    del card["model_id"]

    with pytest.raises(ValueError, match="model_id"):
        publication_mapping({"model_card": card}, QUOTA)


def test_an_invalid_card_is_refused() -> None:
    with pytest.raises(ValueError, match="context_length"):
        publication_mapping({"model_card": model_card(context_length=0)}, QUOTA)


def test_the_publish_request_carries_the_card_to_the_mapping() -> None:
    request = PublishFromQuotaRequest(resource_id="svc-quota", model_card=model_card())

    assert request.listing_request() == {"model_card": model_card()}
