"""The inference contract against the shared market-domain harness."""

from __future__ import annotations

import pytest
from market_core import (
    MARKET_DOMAIN_CONTRACT_VERSION,
    DomainCodecExample,
    DomainConformanceCase,
    assert_domain_conformance,
)
from pydantic import ValidationError

from arkhai_inference.domain_runtime import market_domain
from arkhai_inference.schema import (
    InferenceListing,
    InferenceMaterialization,
    InferenceMessage,
    InferenceReceipt,
    InferenceResult,
    InferenceTerms,
)

_OBLIGATION = "c" * 64
_CARD = {
    "model_id": "meta-llama/llama-3.1-8b-instruct",
    "artifact_ref": "hf://meta-llama/Llama-3.1-8B-Instruct@0e9e39f",
    "provenance": "self-hosted",
    "served_model_name": "llama-3.1-8b",
    "context_length": 131072,
    "quantization": "fp8",
    "architecture": {"modality": "text->text"},
    "supported_parameters": ["tools"],
    "endpoint": {"base_url": "https://inference.acme.example/v1"},
    "rate_card": {"prompt_credits_per_million": 500, "completion_credits_per_million": 1500},
    "capacity_site_id": "site-a",
}
_RATE_CARD = _CARD["rate_card"]
_MESSAGE = {"kind": "inference.v1", "version": 1, "payload": {"quantity": 10, "key": {"mode": "new"}}}
_MATERIALIZATION = {
    "obligation_ref": _OBLIGATION,
    "mechanism": "alkahest.v1",
    "fulfillment_id": "inference-fulfillment.v1:" + "d" * 64,
    "quantity": 10,
    "rate_card": _RATE_CARD,
}
_RECEIPT = {"status": "fulfilled", "obligation_ref": _OBLIGATION}
_RESULT = {"action": "issue"}


def _example(model, value):
    return DomainCodecExample(input=value, expected=model.model_validate(value))


def test_contract_identity_and_version():
    contract = market_domain()
    assert contract.identity == "inference.v1"
    assert contract.contract_version == MARKET_DOMAIN_CONTRACT_VERSION
    assert contract.declared_capabilities == frozenset()


def test_contract_passes_the_shared_conformance_harness():
    assert_domain_conformance(
        DomainConformanceCase(
            contract=market_domain(),
            listing=_example(InferenceListing, {"listing_resource": _CARD}),
            message=_example(InferenceMessage, _MESSAGE),
            terms=_example(InferenceTerms, {**_MESSAGE, "listing_ref": "listing-1"}),
            materialization=_example(InferenceMaterialization, _MATERIALIZATION),
            receipt=_example(InferenceReceipt, _RECEIPT),
            result=_example(InferenceResult, _RESULT),
            capabilities=frozenset(),
        )
    )


def test_codecs_accept_wire_and_model_inputs():
    codecs = market_domain().codecs
    listing = codecs.listing({"listing_resource": _CARD})
    assert codecs.listing(listing) == listing
    assert codecs.message(_MESSAGE).quantity == 10
    assert codecs.terms({**_MESSAGE, "listing_ref": "l"}).listing_ref == "l"
    assert codecs.materialization(_MATERIALIZATION).rate_card.prompt_credits_per_million == 500
    assert codecs.receipt(_RECEIPT).status == "fulfilled"
    assert codecs.result(_RESULT).status == "success"


@pytest.mark.parametrize(
    "codec,value",
    [
        ("listing", {"listing_resource": {**_CARD, "provenance": None}}),
        ("message", {**_MESSAGE, "payload": {"quantity": 0}}),
        ("message", {**_MESSAGE, "buyer_principal": {"scheme": "ed25519", "identifier": "x" * 43}}),
        ("terms", {**_MESSAGE, "kind": "api_credits.v1"}),
        ("materialization", {k: v for k, v in _MATERIALIZATION.items() if k != "rate_card"}),
        ("materialization", {**_MATERIALIZATION, "rate_card": {**_RATE_CARD, "prompt_credits_per_million": 1.5}}),
        ("materialization", {**_MATERIALIZATION, "obligation_ref": None, "escrow_uid": None}),
        ("materialization", {**_MATERIALIZATION, "key_mode": "existing"}),
        ("receipt", {"status": "fulfilled"}),
        ("receipt", {**_RECEIPT, "status": " "}),
        ("result", {"action": " "}),
    ],
)
def test_codecs_reject_invalid_inputs(codec, value):
    with pytest.raises(ValidationError):
        getattr(market_domain().codecs, codec)(value)


def test_materialization_pins_the_rate_card():
    materialization = InferenceMaterialization.model_validate(_MATERIALIZATION)
    assert materialization.rate_card.model_dump() == {
        **_RATE_CARD,
        "request_credits": 0,
        "cached_prompt_credits_per_million": None,
        "image_credits_per_unit": None,
    }
