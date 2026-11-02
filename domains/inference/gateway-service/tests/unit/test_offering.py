"""Selecting the gateway's listing from the storefront and projecting it onto the family's offering."""

from __future__ import annotations

import httpx
import pytest
from arkhai_api.issuance import accepted_terms_digest
from arkhai_api_gate import PurchasePointer
from arkhai_inference.listings import InferenceModelCard, accepted_terms
from storefront_client.client import StorefrontClient

from inference_gateway_service.offering import PAGE_SIZE, OfferingUnavailable, load_offering, project
from tests.cards import (
    QUOTA, REGISTRY_URL, SERVED_MODEL, STOREFRONT_URL, UPSTREAM_URL, Storefront, card, listing, settings, summary,
)


def test_a_listing_projects_onto_its_model_scope_charge_pointer_and_terms():
    offering = project(summary(), settings())

    assert (offering.service, offering.scope_service, offering.scope_resource_id) == (
        SERVED_MODEL, SERVED_MODEL, QUOTA,
    )
    assert offering.default_charge == 3
    assert offering.purchase == PurchasePointer(
        service_name=SERVED_MODEL, listing_id="lst-1", storefront_url=STOREFRONT_URL, registry_url=REGISTRY_URL,
    )
    assert offering.upstream_base_url == UPSTREAM_URL


def test_the_current_terms_digest_as_the_storefront_pins_them():
    # The storefront pins accepted_terms(card) under accepted_terms_digest at issuance.
    pinned = accepted_terms_digest(accepted_terms(InferenceModelCard.model_validate(card())))

    assert accepted_terms_digest(project(summary(), settings()).current_terms) == pinned


@pytest.mark.parametrize(
    ("fields", "cause"),
    [
        ({"rate_card": {"completion_credits_per_million": 5}}, "completion_credits_per_million"),
        ({"rate_card": {"request_credits": 0}}, "request_credits"),
        ({"rate_card": {"request_credits": 2**53}}, "request_credits"),
        ({"served_model_name": ""}, "not a valid inference listing"),
    ],
    ids=["per-token", "no-request-charge", "past-the-digest-bound", "unreadable"],
)
def test_a_card_the_gateway_cannot_charge_per_request_is_refused_naming_why(fields, cause):
    with pytest.raises(OfferingUnavailable, match=cause):
        project(summary(**fields), settings())


def test_the_largest_request_charge_the_digest_carries_is_accepted():
    assert project(summary(rate_card={"request_credits": 2**53 - 1}), settings()).default_charge == 2**53 - 1


async def _load(storefront: Storefront, **fields):
    client = StorefrontClient(STOREFRONT_URL, transport=httpx.MockTransport(storefront.handle))
    try:
        return await load_offering(settings(**fields), client)
    finally:
        await client.close()


def _others(count: int, start: int = 0) -> list[dict]:
    return [listing(f"other-{start + n}", served_model_name="other-model") for n in range(count)]


async def test_the_one_matching_listing_is_selected():
    offering = await _load(Storefront([*_others(2), listing("lst-1"), *_others(1, start=2)]))

    assert offering.purchase.listing_id == "lst-1"


async def test_the_sole_match_is_found_on_a_later_page():
    storefront = Storefront([*_others(PAGE_SIZE), listing("lst-1")])

    offering = await _load(storefront)

    assert offering.purchase.listing_id == "lst-1"
    assert storefront.pages == [(PAGE_SIZE, 0), (PAGE_SIZE, PAGE_SIZE)]


@pytest.mark.parametrize(
    ("listings", "count"),
    [
        (_others(3), 0),
        ([listing("lst-1"), *_others(PAGE_SIZE - 1), listing("lst-2")], 2),
    ],
    ids=["none", "a-duplicate-on-a-later-page"],
)
async def test_none_or_several_matches_are_refused_with_the_count(listings, count):
    with pytest.raises(OfferingUnavailable, match=f"^{count} open listings"):
        await _load(Storefront(listings))


async def test_a_configured_listing_id_is_read_directly():
    storefront = Storefront([listing("lst-1"), listing("lst-2")])

    offering = await _load(storefront, listing_id="lst-2")

    assert offering.purchase.listing_id == "lst-2"
    assert storefront.pages == []


async def test_a_configured_listing_for_another_model_is_refused():
    with pytest.raises(OfferingUnavailable, match="does not offer"):
        await _load(Storefront([listing("lst-1", served_model_name="other-model")]), listing_id="lst-1")


async def test_an_unreadable_storefront_is_refused_naming_it():
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = StorefrontClient(STOREFRONT_URL, transport=httpx.MockTransport(unreachable))
    with pytest.raises(OfferingUnavailable, match="cannot be read"):
        await load_offering(settings(), client)
    await client.close()
