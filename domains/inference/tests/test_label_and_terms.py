"""The inference issuance label and the accepted terms both inference roots build."""

from __future__ import annotations

from arkhai_inference.label import INFERENCE_LABEL
from arkhai_inference.listings import InferenceModelCard, accepted_terms


def _card(**fields) -> InferenceModelCard:
    return InferenceModelCard.model_validate(
        {
            "model_id": "arkhai/stub-instruct",
            "artifact_ref": "dev://arkhai/stub-instruct",
            "provenance": "self-hosted",
            "served_model_name": "stub-instruct",
            "context_length": 8192,
            "quantization": "none",
            "architecture": {"modality": "text->text"},
            "supported_parameters": [],
            "endpoint": {"base_url": "http://gateway.test/v1"},
            "rate_card": {
                "asset": "0x" + "01" * 20,
                "prompt_credits_per_million": 0,
                "completion_credits_per_million": 0,
                "request_credits": 1,
            },
            "capacity_site_id": "default",
            **fields,
        }
    )


def test_the_label_spells_inference_schemas_and_the_default_fulfilment_prefix() -> None:
    assert INFERENCE_LABEL.name == "inference"
    assert INFERENCE_LABEL.fulfillment_id_prefix == "inference-fulfillment.v1"
    assert INFERENCE_LABEL.issuance_request_schema == "arkhai.inference.issuance-request.v1"


def test_the_accepted_terms_are_the_rate_card_and_attestation_as_plain_json() -> None:
    attestation = {"kind": "example.v1", "schema_version": 1, "payload": {}}
    card = _card(attestation=attestation)

    assert accepted_terms(card) == {
        "rate_card": card.rate_card.model_dump(mode="json"),
        "attestation": attestation,
    }
    assert accepted_terms(_card())["attestation"] is None
