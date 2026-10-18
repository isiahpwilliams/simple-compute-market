from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from inference_storefront.domain_runtime import (
    INFERENCE_STOREFRONT_DOMAIN,
    get_market_domain_contract,
)
from arkhai_inference.domain_runtime import market_domain
from arkhai_inference.schema import INFERENCE_SCHEMA_KIND
from market_core import (
    DomainCapability,
    DomainCodecExample,
    DomainConformanceCase,
    assert_domain_conformance,
)
from tests.integration.credit_negotiation import model_card


def test_domain_runtime_normalizes_inference_schema_slots() -> None:
    runtime = market_domain()

    listing = runtime.codecs.listing({**model_card(), "resource_id": "quota-a"})
    message = runtime.codecs.message(
        {
            "kind": "inference.v1",
            "payload": {"quantity": "5", "key": {"mode": "new"}},
        }
    )
    terms = runtime.codecs.terms(
        {
            "kind": "inference.v1",
            "payload": {
                "quantity": 7,
                "key": {"mode": "existing", "key_id": "ik_123"},
            },
            "listing_ref": "listing-1",
        }
    )
    materialization = runtime.codecs.materialization(
        {
            "kind": "inference.v1",
            "escrow_uid": "escrow-1",
            "quantity": 5,
            "rate_card": model_card()["rate_card"],
        }
    )
    receipt = runtime.codecs.receipt(
        {
            "kind": "inference.v1",
            "status": "fulfilled",
            "fulfillment_uid": "fulfill-1",
            "obligation_ref": "ab" * 32,
        }
    )
    result = runtime.codecs.result(
        {
            "kind": "inference.v1",
            "action": "issue_credits",
        }
    )

    assert runtime.identity == INFERENCE_SCHEMA_KIND
    assert listing.listing_resource.served_model_name == "atlas-7b"
    assert listing.listing_resource.resource_id == "quota-a"
    assert listing.listing_resource.capacity_site_id == "tokens"
    assert message.quantity == 5
    assert message.key_mode == "new"
    assert terms.quantity == 7
    assert terms.key_id == "ik_123"
    assert terms.listing_ref == "listing-1"
    assert materialization.quantity == 5
    assert receipt.status == "fulfilled"
    assert result.status == "success"

    assert_domain_conformance(
        DomainConformanceCase(
            contract=runtime,
            listing=DomainCodecExample(listing, listing),
            message=DomainCodecExample(message, message),
            terms=DomainCodecExample(terms, terms),
            materialization=DomainCodecExample(
                materialization,
                materialization,
            ),
            receipt=DomainCodecExample(receipt, receipt),
            result=DomainCodecExample(result, result),
            capabilities=frozenset(),
        )
    )
    assert not runtime.has_capability(
        DomainCapability.COMPUTE_PROVISIONING,
    )
    assert runtime.compute_provisioning is None


def test_domain_runtime_normalizes_listing_resource_from_foreign_model() -> None:
    """Accept models loaded through a second source/wheel import path."""

    class ForeignInferenceResource(BaseModel):
        model_config = ConfigDict(extra="allow")

        kind: str

    listing = market_domain().codecs.listing(
        {
            "listing_resource": ForeignInferenceResource(
                **{**model_card(), "resource_id": "quota-a"}
            ),
        }
    )

    assert listing.listing_resource.served_model_name == "atlas-7b"
    assert listing.listing_resource.resource_id == "quota-a"
    assert listing.listing_resource.capacity_site_id == "tokens"


def test_domain_runtime_normalizes_json_encoded_listing_resource() -> None:
    listing = market_domain().codecs.listing(
        {
            "listing_resource": json.dumps({**model_card(), "resource_id": "quota-a"}),
        }
    )

    assert listing.listing_resource.served_model_name == "atlas-7b"
    assert listing.listing_resource.resource_id == "quota-a"
    assert listing.listing_resource.capacity_site_id == "tokens"


def test_domain_runtime_surfaces_inference_validation_errors() -> None:
    runtime = market_domain()

    with pytest.raises(ValueError, match="quantity"):
        runtime.codecs.message(
            {
                "kind": "inference.v1",
                "payload": {"quantity": 0, "key": {"mode": "new"}},
            }
        )


def test_storefront_resolves_inference_domain_runtime() -> None:
    runtime = get_market_domain_contract()
    assert runtime is INFERENCE_STOREFRONT_DOMAIN

    assert runtime.identity == "inference.v1"
    assert (
        runtime.codecs.message(
            {
                "kind": "inference.v1",
                "payload": {"quantity": 1},
            }
        ).quantity
        == 1
    )
