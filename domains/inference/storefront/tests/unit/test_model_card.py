"""The published model card is the operator's card bound to its quota resource."""

from __future__ import annotations

import pytest

from inference_storefront.model_card import publishable_model_card
from inference_storefront.rate_card_guard import RateCardNotPublishable
from tests.integration.credit_negotiation import model_card


def _operator_card(**overrides):
    card = {k: v for k, v in model_card().items() if k not in {"kind", "offering_mode", "resource_id", "capacity_site_id"}}
    card.update(overrides)
    return card


def test_the_card_is_bound_to_the_resource_and_site():
    card = publishable_model_card(_operator_card(), resource_id="svc-quota", capacity_site_id="tokens")
    assert (card.resource_id, card.capacity_site_id, card.offering_mode) == ("svc-quota", "tokens", "inference")
    assert card.model_id == "acme/atlas-7b"


def test_model_id_is_derived_from_owner_and_name_when_absent():
    operator = _operator_card(owner="Acme", name="Atlas-7B-int4")
    operator.pop("model_id")
    card = publishable_model_card(operator, resource_id="svc-quota", capacity_site_id="tokens")
    assert card.model_id == "acme/atlas-7b"


def test_a_card_without_model_id_or_derivation_inputs_is_refused():
    operator = _operator_card()
    operator.pop("model_id")
    with pytest.raises(ValueError, match="owner and name"):
        publishable_model_card(operator, resource_id="svc-quota", capacity_site_id="tokens")


def test_a_metered_rate_card_is_refused_before_publication():
    operator = _operator_card()
    operator["rate_card"] = {**operator["rate_card"], "completion_credits_per_million": 5}
    with pytest.raises(RateCardNotPublishable, match="completion_credits_per_million"):
        publishable_model_card(operator, resource_id="svc-quota", capacity_site_id="tokens")
