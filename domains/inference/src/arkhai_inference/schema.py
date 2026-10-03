"""Inference market schema and public domain vocabulary."""

from __future__ import annotations

import json
from typing import Any, Literal

from market_core.schemas import SettlementOption, SettlementSelection
from market_identity import Identity
from pydantic import BaseModel, ConfigDict, Field, model_validator

from arkhai_inference.listings.models import (
    INFERENCE_KIND,
    InferenceModelCard,
    InferenceRateCard,
)
from arkhai_inference.negotiation.terms import (
    INFERENCE_PROVISION_KIND,
    InferenceProvisionTerms,
)

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


class InferenceMessage(InferenceProvisionTerms):
    """Inference negotiation message payload."""

    model_config = ConfigDict(extra="forbid")

    settlement_selection: SettlementSelection | None = None
    buyer_principal: Identity | None = None
    seller_principal: Identity | None = None

    kind: Literal["inference.v1"] = INFERENCE_PROVISION_KIND

    @model_validator(mode="after")
    def _validate_message(self) -> "InferenceMessage":
        if self.quantity is None or self.quantity < 1:
            raise ValueError("payload.quantity must be >= 1")
        if self.key_mode not in {"new", "existing"}:
            raise ValueError("payload.key.mode must be 'new' or 'existing'")
        if self.key_mode == "existing" and not self.key_id:
            raise ValueError("payload.key.key_id is required for existing keys")
        selected_fields = (
            self.settlement_selection,
            self.buyer_principal,
            self.seller_principal,
        )
        if any(value is not None for value in selected_fields) and any(
            value is None for value in selected_fields
        ):
            raise ValueError(
                "settlement selection and canonical buyer/seller principals "
                "must be recorded together"
            )
        return self


class InferenceTerms(InferenceMessage):
    """Canonical agreed inference terms produced by negotiation."""

    listing_ref: str | None = None


class InferenceMaterialization(BaseModel):
    """Settlement-to-fulfillment handoff for an inference agreement.

    ``rate_card`` is the card in force at issuance; the grant pins it so a
    later republication cannot reprice a balance already sold.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inference.v1"] = INFERENCE_SCHEMA_KIND
    escrow_uid: str | None = None
    quantity: int = Field(ge=1)
    key_mode: Literal["new", "existing"] = "new"
    key_id: str | None = None
    rate_card: InferenceRateCard
    listing_resource: InferenceModelCard | None = None
    settlement_ref: dict[str, Any] | None = None
    obligation_ref: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    fulfillment_id: str | None = Field(default=None, min_length=1)
    mechanism: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_materialization(self) -> "InferenceMaterialization":
        if self.escrow_uid is not None and not self.escrow_uid.strip():
            raise ValueError("escrow_uid must be non-empty")
        if self.escrow_uid is None and self.obligation_ref is None:
            raise ValueError("materialization requires escrow_uid or obligation_ref")
        if self.obligation_ref is not None and (
            self.mechanism is None or self.fulfillment_id is None
        ):
            raise ValueError(
                "mechanism-neutral materialization requires mechanism and fulfillment_id"
            )
        if self.key_mode == "existing" and not self.key_id:
            raise ValueError("key_id is required for existing keys")
        return self


class InferenceReceipt(BaseModel):
    """Domain receipt for inference issuance/fulfillment state."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inference.v1"] = INFERENCE_SCHEMA_KIND
    status: str
    escrow_uid: str | None = None
    obligation_ref: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mechanism: str | None = None
    capacity_reservation_id: str | None = None
    key_id: str | None = None
    fulfillment_uid: str | None = None
    fulfillment_id: str | None = None
    credentials_ref: dict[str, Any] | None = None
    result_ref: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_receipt(self) -> "InferenceReceipt":
        if self.escrow_uid is None and self.obligation_ref is None:
            raise ValueError("receipt requires escrow_uid or obligation_ref")
        if not self.status.strip():
            raise ValueError("status must be non-empty")
        return self


class InferenceResult(BaseModel):
    """Result shape for inference issuance/fulfillment slots."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["inference.v1"] = INFERENCE_SCHEMA_KIND
    action: str
    status: str = "success"
    fulfillment_uid: str | None = None
    obligation_ref: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mechanism: str | None = None
    fulfillment_id: str | None = None
    credentials_ref: dict[str, Any] | None = None
    details: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> "InferenceResult":
        if not self.action.strip():
            raise ValueError("action must be non-empty")
        if not self.status.strip():
            raise ValueError("status must be non-empty")
        return self
