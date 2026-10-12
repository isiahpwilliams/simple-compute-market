"""Inference usage records and charge derivation.

A record is what one request consumed; ``derive_charge`` is the domain's
deterministic interpretation of it against the grant's pinned rate card, so
independent gates agree on the integer. ``prompt_tokens`` excludes the cached
prompt tokens counted separately.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from arkhai_inference.listings.models import InferenceRateCard

UsageOutcome = Literal["completed", "cancelled", "failed"]
USAGE_OUTCOMES: tuple[str, ...] = get_args(UsageOutcome)

_TOKENS_PER_UNIT = 1_000_000
_SAFE_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$"


class InferenceUsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(pattern=_SAFE_REF_PATTERN)
    key_id: str = Field(pattern=_SAFE_REF_PATTERN)
    request_id: str = Field(pattern=_SAFE_REF_PATTERN)
    prompt_tokens: StrictInt = Field(ge=0)
    completion_tokens: StrictInt = Field(ge=0)
    cached_prompt_tokens: StrictInt = Field(default=0, ge=0)
    image_units: StrictInt = Field(default=0, ge=0)
    outcome: UsageOutcome


def derive_charge(record: InferenceUsageRecord, rate_card: InferenceRateCard) -> int:
    """Base units one record costs under one card; zero when the upstream failed."""
    if record.outcome == "failed":
        return 0
    per_million = (
        record.prompt_tokens * rate_card.prompt_credits_per_million
        + record.completion_tokens * rate_card.completion_credits_per_million
        + record.cached_prompt_tokens * (rate_card.cached_prompt_credits_per_million or 0)
    )
    token_charge = -(-per_million // _TOKENS_PER_UNIT)
    image_charge = record.image_units * (rate_card.image_credits_per_unit or 0)
    return token_charge + image_charge + rate_card.request_credits
