"""Only a request-priced rate card is publishable, while the gate charges a fixed amount per request."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arkhai_inference.listings import InferenceRateCard, non_request_priced_rate


def request_priced_guard(listing_resource: Mapping[str, Any]) -> str | None:
    """Why the card's rate card may not be published, naming the field, or ``None``."""
    field = non_request_priced_rate(InferenceRateCard.model_validate(listing_resource["rate_card"]))
    if field is None:
        return None
    if field == "request_credits":
        return (
            "rate_card.request_credits must be between 1 and 2**53 - 1: "
            "the gate charges it per request"
        )
    return f"rate_card.{field} must be zero: the gate charges a fixed amount per request"
