"""The inference settle request: the family's, under the component name this storefront serves."""

from __future__ import annotations

from arkhai_api_selling.route_services import QuotaSettleRequest


class InferenceSettleRequest(QuotaSettleRequest):
    """Settlement input for Alkahest by negotiation ID."""
