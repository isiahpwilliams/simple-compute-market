"""The model card an inference listing publishes, built from the operator's card over its quota resource."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arkhai_inference.listings import (
    INFERENCE_KIND,
    INFERENCE_OFFERING_MODE,
    InferenceModelCard,
    derive_model_id,
)

from inference_storefront.rate_card_guard import require_request_priced


def publishable_model_card(
    card: Mapping[str, Any],
    *,
    resource_id: str,
    capacity_site_id: str,
) -> InferenceModelCard:
    """Validate the card and bind it to the quota resource and site it derives from.

    ``model_id`` is taken as given, or derived from ``owner`` and ``name`` with
    the contract's rule when the card names those instead.
    """
    fields = dict(card)
    owner = fields.pop("owner", None)
    name = fields.pop("name", None)
    if not fields.get("model_id"):
        if not owner or not name:
            raise ValueError("model card requires model_id, or owner and name to derive it")
        fields["model_id"] = derive_model_id(str(owner), str(name))
    fields.update(
        kind=INFERENCE_KIND,
        offering_mode=INFERENCE_OFFERING_MODE,
        resource_id=resource_id,
        capacity_site_id=capacity_site_id,
    )
    model_card = InferenceModelCard.model_validate(fields)
    require_request_priced(model_card.rate_card)
    return model_card
