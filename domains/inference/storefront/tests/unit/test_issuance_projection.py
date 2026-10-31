"""The issuance projection: the served model, its quota, and the terms the key is pinned to."""

from __future__ import annotations

from arkhai_api.issuance import accepted_terms_digest

from inference_storefront.issuance import issuance_projection
from tests.cards import bound_card

ATTESTATION = {"kind": "example.v1", "schema_version": 1, "payload": {"claim": "x"}}


def test_the_subject_names_the_served_model_and_the_card_endpoint() -> None:
    subject = issuance_projection(bound_card())

    assert subject.service == "stub-instruct"
    assert subject.resource_id == "svc-quota"
    assert subject.endpoint == "http://gateway.test/v1"


def test_the_accepted_terms_are_the_cards_rate_card_and_attestation() -> None:
    card = bound_card(attestation=ATTESTATION)

    subject = issuance_projection(card)

    assert subject.accepted_terms == {
        "rate_card": {
            "asset": card["rate_card"]["asset"],
            "prompt_credits_per_million": "0",
            "completion_credits_per_million": "0",
            "request_credits": "3",
            "cached_prompt_credits_per_million": None,
            "image_credits_per_unit": None,
        },
        "attestation": ATTESTATION,
    }
    assert subject.terms_digest == accepted_terms_digest(dict(subject.accepted_terms))
    assert subject.request_charge == 3


def test_a_card_with_no_attestation_pins_none() -> None:
    assert issuance_projection(bound_card()).accepted_terms["attestation"] is None


def test_two_listings_of_one_model_under_different_served_names_project_different_services() -> None:
    first = issuance_projection(bound_card(served_model_name="stub-instruct"))
    second = issuance_projection(bound_card(served_model_name="stub-instruct-long"))

    assert first.service != second.service


def test_another_rate_is_another_digest() -> None:
    cheap = issuance_projection(bound_card())
    dear = bound_card()
    dear["rate_card"] = {**dear["rate_card"], "request_credits": 4}

    assert issuance_projection(dear).terms_digest != cheap.terms_digest
