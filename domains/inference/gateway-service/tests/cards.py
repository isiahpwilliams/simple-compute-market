"""Listings the gateway tests read. Every address is a deterministic development value."""

from __future__ import annotations

from typing import Any

import httpx
from storefront_client.models import ListingSummary

from inference_gateway_service.config import GatewaySettings

ASSET = "0x" + "01" * 20
SERVED_MODEL = "stub-instruct"
QUOTA = "stub-instruct-quota"
STOREFRONT_URL = "http://storefront.test"
REGISTRY_URL = "http://registry.test"
UPSTREAM_URL = "http://model.test/v1"


def card(**fields: Any) -> dict[str, Any]:
    """A published card bound to its quota."""
    rate_card = {
        "asset": ASSET,
        "prompt_credits_per_million": 0,
        "completion_credits_per_million": 0,
        "request_credits": 3,
        **fields.pop("rate_card", {}),
    }
    return {
        "kind": "inference.v1",
        "model_id": "arkhai/stub-instruct",
        "artifact_ref": "dev://arkhai/stub-instruct",
        "provenance": "self-hosted",
        "served_model_name": SERVED_MODEL,
        "context_length": 8192,
        "quantization": "none",
        "architecture": {"modality": "text->text"},
        "supported_parameters": ["max_tokens", "stream"],
        "endpoint": {"base_url": "http://gateway.test/v1"},
        "rate_card": rate_card,
        "resource_id": QUOTA,
        "capacity_site_id": "inference",
        "offering_mode": "inference",
        **fields,
    }


def listing(listing_id: str = "lst-1", **fields: Any) -> dict[str, Any]:
    return {"listing_id": listing_id, "status": "open", "listing_resource": card(**fields)}


def summary(listing_id: str = "lst-1", **fields: Any) -> ListingSummary:
    return ListingSummary.from_dict(listing(listing_id, **fields))


def settings(**fields: Any) -> GatewaySettings:
    return GatewaySettings(
        storefront_url=STOREFRONT_URL,
        registry_url=REGISTRY_URL,
        resource_id=QUOTA,
        served_model_name=SERVED_MODEL,
        upstream_base_url=UPSTREAM_URL,
        **fields,
    )


class Storefront:
    """Serves the listings route over pages, and a single listing by id."""

    def __init__(self, listings: list[dict]) -> None:
        self.listings = listings
        self.pages: list[tuple[int, int]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/listings":
            limit, offset = int(request.url.params["limit"]), int(request.url.params["offset"])
            self.pages.append((limit, offset))
            page = self.listings[offset:offset + limit]
            return httpx.Response(200, json={"listings": page, "count": len(page), "limit": limit, "offset": offset})
        listing_id = request.url.path.rsplit("/", 1)[-1]
        found = [entry for entry in self.listings if entry["listing_id"] == listing_id]
        return httpx.Response(200, json=found[0]) if found else httpx.Response(404, json={"detail": "not found"})
