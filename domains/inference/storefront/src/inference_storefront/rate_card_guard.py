"""Only request-priced rate cards are publishable while the gate charges a fixed amount per request."""

from __future__ import annotations

from arkhai_inference.listings import InferenceRateCard

METERED_RATE_FIELDS = (
    "prompt_credits_per_million",
    "cached_prompt_credits_per_million",
    "completion_credits_per_million",
    "image_credits_per_unit",
)


class RateCardNotPublishable(ValueError):
    """The rate card advertises a price this stack does not charge."""


def require_request_priced(rate_card: InferenceRateCard) -> InferenceRateCard:
    for field in METERED_RATE_FIELDS:
        if getattr(rate_card, field):
            raise RateCardNotPublishable(
                f"rate card {field} must be zero: the gate charges a fixed amount per request"
            )
    return rate_card
