"""The listing the gateway fronts, read from the storefront and projected onto the family's offering."""

from __future__ import annotations

from typing import Any

import httpx
from arkhai_api_gate import PurchasePointer
from arkhai_api_gateway import GatewayOffering
from arkhai_inference.listings import accepted_terms, coerce_resource_dict, non_request_priced_rate
from arkhai_inference.schema import InferenceListing
from pydantic import ValidationError
from storefront_client.client import StorefrontClient, StorefrontClientError
from storefront_client.models import ListingSummary

from inference_gateway_service.config import GatewaySettings

#: The storefront listing route's largest page.
PAGE_SIZE = 200


class OfferingUnavailable(Exception):
    """The gateway cannot serve yet; the message names the cause."""


async def load_offering(settings: GatewaySettings, storefront: StorefrontClient) -> GatewayOffering:
    """Select the listing ``settings`` names and project it, or refuse naming why."""
    try:
        listing = await _select(settings, storefront)
    except (StorefrontClientError, httpx.HTTPError) as error:
        raise OfferingUnavailable(f"the storefront's listings cannot be read: {error}") from error
    return project(listing, settings)


async def _select(settings: GatewaySettings, storefront: StorefrontClient) -> ListingSummary:
    if settings.listing_id is not None:
        listing = await storefront.get_listing(settings.listing_id)
        if not _names(listing, settings):
            raise OfferingUnavailable(
                f"listing {settings.listing_id} does not offer {settings.served_model_name} "
                f"on {settings.resource_id}"
            )
        return listing
    matches: list[ListingSummary] = []
    offset = 0
    while True:
        page = await storefront.list_listings(status="open", limit=PAGE_SIZE, offset=offset)
        matches.extend(listing for listing in page.listings if _names(listing, settings))
        if len(page.listings) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    if len(matches) != 1:
        raise OfferingUnavailable(
            f"{len(matches)} open listings offer {settings.served_model_name} on "
            f"{settings.resource_id}; the gateway fronts exactly one"
        )
    return matches[0]


def _names(listing: ListingSummary, settings: GatewaySettings) -> bool:
    card: dict[str, Any] = coerce_resource_dict(listing.listing_resource)
    return (
        card.get("resource_id") == settings.resource_id
        and card.get("served_model_name") == settings.served_model_name
    )


def project(listing: ListingSummary, settings: GatewaySettings) -> GatewayOffering:
    """The offering for ``listing``: its model, scope, charge, purchase pointer, and current terms."""
    try:
        card = InferenceListing.model_validate(
            {"listing_resource": coerce_resource_dict(listing.listing_resource)},
        ).listing_resource
    except ValidationError as error:
        raise OfferingUnavailable(
            f"listing {listing.listing_id} is not a valid inference listing: {error}"
        ) from error
    if (field := non_request_priced_rate(card.rate_card)) is not None:
        raise OfferingUnavailable(
            f"listing {listing.listing_id} is not priced per request: {field}"
        )
    return GatewayOffering(
        service=card.served_model_name,
        scope_service=card.served_model_name,
        scope_resource_id=card.resource_id,
        default_charge=card.rate_card.request_credits,
        purchase=PurchasePointer(
            service_name=card.served_model_name,
            listing_id=listing.listing_id,
            storefront_url=settings.storefront_url,
            registry_url=settings.registry_url,
        ),
        upstream_base_url=settings.upstream_base_url,
        upstream_credential_file=settings.upstream_credential_file,
        current_terms=accepted_terms(card),
    )
