"""Inference model card and listing validation."""

from __future__ import annotations

import json

import pytest
from market_core.schemas import RateValue, derive_settlement_option_id
from market_identity import Ed25519Signer
from pydantic import ValidationError

from arkhai_inference.listings.models import (
    INFERENCE_KIND,
    INFERENCE_OFFERING_MODE,
    InferenceModelCard,
    InferenceRateCard,
    coerce_resource_dict,
    resource_is_inference,
)
from arkhai_inference.schema import InferenceListing

_OWNER = Ed25519Signer(bytes(range(32))).identity
_RATES = [RateValue(field="amount", per="credit", value=1)]
_OPTION = {
    "option_id": derive_settlement_option_id(
        mechanism="alkahest.v1", asset="0x" + "01" * 20, rates=_RATES, params={}
    ),
    "mechanism": "alkahest.v1",
    "asset": "0x" + "01" * 20,
    "rates": [rate.model_dump(mode="json") for rate in _RATES],
    "params": {},
}
_REQUIRED = [
    "model_id",
    "artifact_ref",
    "provenance",
    "served_model_name",
    "context_length",
    "quantization",
    "architecture",
    "supported_parameters",
    "endpoint",
    "rate_card",
    "capacity_site_id",
]


def _card(**overrides):
    card = {
        "model_id": "meta-llama/llama-3.1-8b-instruct",
        "artifact_ref": "hf://meta-llama/Llama-3.1-8B-Instruct@0e9e39f",
        "provenance": "self-hosted",
        "served_model_name": "llama-3.1-8b",
        "context_length": 131072,
        "quantization": "fp8",
        "architecture": {"modality": "text->text"},
        "supported_parameters": ["tools", "response_format"],
        "endpoint": {"base_url": "https://inference.acme.example/v1"},
        "rate_card": {
            "prompt_credits_per_million": 500,
            "completion_credits_per_million": 1500,
        },
        "capacity_site_id": "site-a",
    }
    card.update(overrides)
    return card


def test_complete_card_validates_with_defaults():
    card = InferenceModelCard.model_validate(_card())
    assert card.kind == INFERENCE_KIND
    assert card.offering_mode == INFERENCE_OFFERING_MODE
    assert card.endpoint.api_style == "openai.v1"
    assert card.rate_card.request_credits == 0
    assert card.attestation is None
    assert card.model_owner is None


@pytest.mark.parametrize("field", _REQUIRED)
def test_missing_required_field_is_rejected_by_name(field):
    payload = _card()
    del payload[field]
    with pytest.raises(ValidationError) as exc:
        InferenceModelCard.model_validate(payload)
    assert field in str(exc.value)


def test_offering_mode_is_pinned():
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(_card(offering_mode="api_credits"))


def test_api_style_is_pinned():
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(
            _card(endpoint={"base_url": "https://x.example", "api_style": "grpc"})
        )


def test_listing_round_trips_through_json_text():
    listing = InferenceListing.model_validate(
        {"listing_resource": json.dumps(_card()), "settlement_options": [_OPTION]}
    )
    stored = json.dumps(listing.model_dump(mode="json"))
    assert InferenceListing.model_validate(json.loads(stored)) == listing


def test_bare_resource_dict_is_lifted_into_a_listing():
    listing = InferenceListing.model_validate(_card())
    assert listing.listing_resource.model_id == "meta-llama/llama-3.1-8b-instruct"


@pytest.mark.parametrize("provenance", [None, "hosted-for-owner", ""])
def test_provenance_must_be_in_the_enumeration(provenance):
    payload = _card()
    if provenance is None:
        del payload["provenance"]
    else:
        payload["provenance"] = provenance
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(payload)


def test_resold_is_a_legitimate_provenance():
    assert InferenceModelCard.model_validate(_card(provenance="resold")).provenance == "resold"


@pytest.mark.parametrize("quantization", ["q4_k_m", "FP8", ""])
def test_quantization_must_be_in_the_enumeration(quantization):
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(_card(quantization=quantization))


def test_two_sellers_may_share_a_model_id():
    first = InferenceModelCard.model_validate(_card())
    second = InferenceModelCard.model_validate(
        _card(
            artifact_ref="hf://meta-llama/Llama-3.1-8B-Instruct@1c2d3e4",
            quantization="bf16",
            rate_card={
                "prompt_credits_per_million": 900,
                "completion_credits_per_million": 2700,
            },
        )
    )
    assert first.model_id == second.model_id
    assert first.quantization != second.quantization
    assert first.rate_card != second.rate_card


def test_attestation_envelope_does_not_change_the_card():
    plain = InferenceModelCard.model_validate(_card())
    attested = InferenceModelCard.model_validate(
        _card(attestation={"kind": "tee.example", "schema_version": 1, "payload": {"x": 1}})
    )
    assert attested.attestation is not None
    assert attested.model_dump(exclude={"attestation"}) == plain.model_dump(
        exclude={"attestation"}
    )


def test_attestation_envelope_requires_kind_and_version():
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(_card(attestation={"payload": {}}))


def test_model_owner_is_a_marketplace_principal():
    card = InferenceModelCard.model_validate(_card(model_owner=_OWNER.model_dump(mode="json")))
    assert card.model_owner == _OWNER


def test_model_id_is_seller_asserted_but_must_be_filter_safe():
    assert InferenceModelCard.model_validate(_card(model_id="Meta/Llama")).model_id == "Meta/Llama"
    for bad in ["", " meta/llama", "meta llama", "meta/llama?x"]:
        with pytest.raises(ValidationError):
            InferenceModelCard.model_validate(_card(model_id=bad))


def test_artifact_digest_must_be_sha256():
    assert InferenceModelCard.model_validate(
        _card(artifact_digest="sha256:" + "ab" * 32)
    ).artifact_digest.startswith("sha256:")
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(_card(artifact_digest="md5:abc"))


@pytest.mark.parametrize("value", [1.5, -1, True, "500"])
def test_rate_card_admits_only_non_negative_integers(value):
    with pytest.raises(ValidationError):
        InferenceRateCard.model_validate(
            {"prompt_credits_per_million": value, "completion_credits_per_million": 0}
        )


def test_blank_strings_are_rejected():
    for field in ("served_model_name", "artifact_ref", "capacity_site_id"):
        with pytest.raises(ValidationError):
            InferenceModelCard.model_validate(_card(**{field: "   "}))
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(_card(supported_parameters=["tools", " "]))


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        InferenceModelCard.model_validate(_card(royalty_bps=100))


def test_duplicate_settlement_option_ids_are_rejected():
    with pytest.raises(ValidationError):
        InferenceListing.model_validate(
            {"listing_resource": _card(), "settlement_options": [_OPTION, _OPTION]}
        )


def test_retired_offer_resource_key_is_rejected():
    with pytest.raises(ValidationError):
        InferenceListing.model_validate({"offer_resource": _card()})


def test_resource_helpers():
    stored = InferenceModelCard.model_validate(_card()).model_dump(mode="json")
    assert resource_is_inference(stored)
    assert resource_is_inference(json.dumps(stored))
    assert not resource_is_inference(_card())
    assert resource_is_inference(InferenceModelCard.model_validate(_card()))
    assert not resource_is_inference({"kind": "api_credits.v1"})
    assert coerce_resource_dict("not json") == {}
    assert coerce_resource_dict(None) == {}
