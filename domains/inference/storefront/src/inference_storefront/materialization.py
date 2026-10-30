"""The delivery's public materialization: the accepted card and the rate card the key was sold at."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arkhai_api.issuance import IssuanceResult
from arkhai_api_selling.contributions import DeliveryContext
from arkhai_inference.listings import InferenceModelCard, coerce_resource_dict
from arkhai_inference.schema import InferenceMaterialization

PUBLIC_RESULT_KEY = "materialization"


def public_result_extension(
    listing_resource: Mapping[str, Any], result: IssuanceResult, delivery: DeliveryContext
) -> dict[str, Any]:
    """The contract's materialization of the accepted listing, under one key.

    The listing is the one the kit recorded at acceptance, so a republication
    at another rate does not change what the buyer is shown. The settlement
    reference is the Alkahest escrow uid, the only mechanism this storefront
    composes.
    """
    card = InferenceModelCard.model_validate(coerce_resource_dict(listing_resource))
    materialization = InferenceMaterialization(
        listing_resource=card,
        rate_card=card.rate_card,
        escrow_uid=delivery.settlement_ref,
        quantity=result.quantity,
        key_mode=result.key_mode,
        key_id=result.key_id,
        fulfillment_id=result.fulfillment_id,
        mechanism=delivery.mechanism,
    )
    return {PUBLIC_RESULT_KEY: materialization.model_dump(mode="json", exclude_none=True)}
