"""The model-card rendering the plugin contributes."""

from __future__ import annotations

from arkhai_inference_buyer.cli import CONTRIBUTIONS

_CARD = {
    "kind": "inference.v1",
    "model_id": "arkhai/stub-instruct",
    "artifact_ref": "dev://arkhai/stub-instruct",
    "display_name": "Arkhai stub instruct",
    "provenance": "self-hosted",
    "served_model_name": "stub-instruct",
    "context_length": 8192,
    "quantization": "none",
    "endpoint": {"base_url": "http://inference-gateway:8105/v1"},
    "rate_card": {"asset": "0xabc", "prompt_credits_per_million": 0, "completion_credits_per_million": 0, "request_credits": 1},
}


def test_summary_names_the_model_and_the_served_name_when_they_differ():
    rendering = CONTRIBUTIONS.rendering
    assert rendering.summary_header == "Model"
    assert rendering.summary(rendering.resource(_CARD)) == "arkhai/stub-instruct (as stub-instruct)"
    assert rendering.summary({**_CARD, "served_model_name": "arkhai/stub-instruct"}) == "arkhai/stub-instruct"
    assert rendering.summary(rendering.resource("not json")) == "-"


def test_columns_are_quantization_context_provenance_and_request_charge():
    rendering = CONTRIBUTIONS.rendering
    assert [(header, value(_CARD)) for header, value in rendering.columns] == [
        ("Quantization", "none"),
        ("Context", "8192"),
        ("Provenance", "self-hosted"),
        ("Per request", "1"),
    ]


def test_details_carry_the_cards_fields():
    details = dict(CONTRIBUTIONS.rendering.details(_CARD))
    assert details["Served as"] == "stub-instruct"
    assert details["Base URL"] == "http://inference-gateway:8105/v1"
    assert details["Rate asset"] == "0xabc"
    assert details["Request charge"] == "1"
    assert details["Attestation"] == "-"
