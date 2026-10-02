"""The inference specification served by the real registry app.

Runs the registry against the packaged inference filter specification with its
database, through the canonical `RegistryClient` over `ASGITransport`: a valid
model-card listing publishes and is found by each declared filter, the dry run
refuses the shapes the specification exists to refuse, and the publish
boundary refuses the retired shape key. Full shape enforcement at publish is
deliberately not this registry's posture (see `reject_retired_listing_shape`);
the storefront's domain codec is where a malformed card is stopped.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from registry_client import ListingRequest, ValidatePublishRequest
from core_registry.api import filter_spec as filter_spec_module
from core_registry.api import validate_routes

pytestmark = pytest.mark.asyncio

_REPO_ROOT = Path(__file__).resolve().parents[4]
_INFERENCE_SPEC = _REPO_ROOT / "domains/inference/registry/filter-spec.yaml"
_ASSET = "0x" + "22" * 20
_ESCROW = {
    "chain_name": "anvil",
    "escrow_address": "0x" + "11" * 20,
    "literal_fields": {"token": _ASSET},
}
_OPTION = {
    "option_id": "a" * 64,
    "mechanism": "alkahest.v1",
    "asset": _ASSET,
    "rates": [{"field": "amount", "per": "credit", "value": "1"}],
    "params": {},
}


def _card(**overrides):
    card = {
        "kind": "inference.v1",
        "model_id": "meta-llama/llama-3.1-8b-instruct",
        "artifact_ref": "hf://meta-llama/Llama-3.1-8B-Instruct@0e9e39f",
        "provenance": "self-hosted",
        "served_model_name": "llama-3.1-8b",
        "model_family": "llama-3.1",
        "context_length": 131072,
        "quantization": "fp8",
        "architecture": {"modality": "text->text"},
        "supported_parameters": ["tools", "response_format"],
        "endpoint": {"base_url": "https://inference.example/v1", "api_style": "openai.v1"},
        "rate_card": {"prompt_credits_per_million": 500, "completion_credits_per_million": 1500},
        "capacity_site_id": "site-a",
        "offering_mode": "inference",
    }
    card.update(overrides)
    return card


@pytest.fixture
def served_inference_spec(monkeypatch):
    # The loader and the dry-run validator cache independently; both must be
    # cleared or a later test validates against this specification.
    monkeypatch.setenv("REGISTRY_FILTER_SPEC_PATH", str(_INFERENCE_SPEC))
    filter_spec_module.reset_cache()
    validate_routes._reset_cache()
    yield filter_spec_module.get_loaded_spec()
    monkeypatch.delenv("REGISTRY_FILTER_SPEC_PATH", raising=False)
    filter_spec_module.reset_cache()
    validate_routes._reset_cache()


async def _publish(registry_client, listing_id, card):
    await registry_client.publish_listing(
        ListingRequest(
            listing_id=listing_id,
            listing_resource=card,
            accepted_escrows=[_ESCROW],
            settlement_options=[_OPTION],
            storefront_url="http://seller",
        )
    )


async def _ids(registry_client, **query):
    matched = await registry_client.list_listings(**query)
    return {str(row.id) for row in matched.listings}


async def test_spec_identity(served_inference_spec):
    assert served_inference_spec.schema_identity.id == "inference"
    assert "listing_resource" in served_inference_spec.listing_shape["required"]


async def test_a_model_card_publishes_and_each_filter_finds_it(
    served_inference_spec, registry_client
):
    await _publish(registry_client, "inference-1", _card())
    await _publish(registry_client, "inference-2", _card(
        quantization="bf16",
        provenance="resold",
        context_length=8192,
        rate_card={"prompt_credits_per_million": 900, "completion_credits_per_million": 2700},
    ))

    assert await _ids(registry_client, model_id="meta-llama/llama-3.1-8b-instruct") == {"inference-1", "inference-2"}
    assert await _ids(registry_client, quantization="fp8") == {"inference-1"}
    assert await _ids(registry_client, provenance="resold") == {"inference-2"}
    assert await _ids(registry_client, modality="text->text") == {"inference-1", "inference-2"}
    assert await _ids(registry_client, supported_parameter="tools") == {"inference-1", "inference-2"}
    assert await _ids(registry_client, context_length_min="65536") == {"inference-1"}
    assert await _ids(registry_client, prompt_credits_max="600") == {"inference-1"}
    assert await _ids(registry_client, completion_credits_max="3000") == {"inference-1", "inference-2"}
    assert await _ids(registry_client, settlement_asset=_ASSET) == {"inference-1", "inference-2"}
    assert await _ids(registry_client, offering_mode="inference") == {"inference-1", "inference-2"}

    fetched = await registry_client.get_listing("inference-1")
    assert fetched.listing_resource["rate_card"]["prompt_credits_per_million"] == 500


async def test_attestation_is_admitted_and_not_filterable(served_inference_spec, registry_client):
    await _publish(registry_client, "attested", _card(
        attestation={"kind": "tee.example", "schema_version": 1, "payload": {"quote": "x"}}
    ))
    assert await _ids(registry_client, model_id="meta-llama/llama-3.1-8b-instruct") == {"attested"}
    assert "attestation" not in {f.name for f in served_inference_spec.filters}


async def _dry_run(registry_client, card):
    return await registry_client.validate_publish_listing(
        ValidatePublishRequest(
            listing_id="candidate",
            listing_resource=card,
            accepted_escrows=[_ESCROW],
            settlement_options=[_OPTION],
            storefront_url="http://seller",
        )
    )


async def test_a_complete_card_passes_the_dry_run(served_inference_spec, registry_client):
    response = await _dry_run(registry_client, _card())
    assert response.valid is True
    assert response.errors == []


@pytest.mark.parametrize(
    "card,field",
    [
        ({k: v for k, v in _card().items() if k != "rate_card"}, "rate_card"),
        ({k: v for k, v in _card().items() if k != "provenance"}, "provenance"),
        (_card(quantization="q4_k_m"), "quantization"),
        (_card(offering_mode="api_credits"), "offering_mode"),
    ],
    ids=["no-rate-card", "no-provenance", "bad-quantization", "wrong-offering-mode"],
)
async def test_malformed_cards_fail_the_dry_run(served_inference_spec, registry_client, card, field):
    response = await _dry_run(registry_client, card)
    assert response.valid is False
    assert any(field in error for error in response.errors), response.errors


async def test_retired_shape_key_is_refused(served_inference_spec, registry_client):
    with pytest.raises(Exception):
        await registry_client.publish_listing(
            ListingRequest.model_validate({
                "listing_id": "old",
                "offer_resource": _card(),
                "accepted_escrows": [_ESCROW],
                "storefront_url": "http://seller",
            })
        )
