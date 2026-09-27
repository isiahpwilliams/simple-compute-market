"""Inference market schema and public domain vocabulary."""

from __future__ import annotations

import json
from typing import Any, Literal

from market_core.schemas import SettlementOption
from pydantic import BaseModel, ConfigDict, Field, model_validator

from domains.inference.listings.models import INFERENCE_KIND, InferenceModelCard

INFERENCE_SCHEMA_KIND = INFERENCE_KIND


class InferenceListing(BaseModel):
    """Inference domain payload carried by a registry listing."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inference.v1"] = INFERENCE_SCHEMA_KIND
    listing_resource: InferenceModelCard = Field(
        description="One served model offered by the seller.",
    )
    accepted_escrows: list[dict[str, Any]] = Field(default_factory=list)
    settlement_options: list[SettlementOption] = Field(default_factory=list)
    demands: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_listing_resource_payload(cls, value: Any) -> Any:
        # Domain models can cross a source/wheel import boundary in the
        # storefront image. Structurally identical Pydantic classes loaded
        # from those two locations do not pass isinstance validation, so
        # normalize models back to their wire representation first.
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        if not isinstance(value, dict):
            return value
        if "listing_resource" in value:
            listing_resource = value["listing_resource"]
            if isinstance(listing_resource, BaseModel):
                listing_resource = listing_resource.model_dump(mode="json")
            elif isinstance(listing_resource, str):
                try:
                    listing_resource = json.loads(listing_resource)
                except (TypeError, ValueError):
                    return value
            return {**value, "listing_resource": listing_resource}
        return {"listing_resource": value}

    @model_validator(mode="after")
    def _validate_listing(self) -> "InferenceListing":
        option_ids = [option.option_id for option in self.settlement_options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("settlement_options contains duplicate option identities")
        return self
