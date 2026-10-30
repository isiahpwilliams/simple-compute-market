"""The model card an inference listing publishes, bound to the quota resource it is created over."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arkhai_api_selling.contributions import QuotaSource
from arkhai_api_selling.publish_route import PublishFromQuotaRequest as QuotaPublishRequest
from arkhai_inference.listings import InferenceModelCard, derive_model_id


class PublishFromQuotaRequest(QuotaPublishRequest):
    """Seller's quota-backed publish request, carrying the card the listing publishes."""

    model_card: dict[str, Any]


def publication_mapping(request: Mapping[str, Any], quota: QuotaSource) -> dict[str, Any]:
    """The operator's card with its resource, site, and mode taken from ``quota``.

    The three are overwritten rather than compared, so a card cannot name
    another resource than the one its quota backs. ``model_id`` is taken as
    given, or derived from ``owner`` and ``name`` by the contract's rule when
    the card names those instead.
    """
    fields = dict(request["model_card"])
    owner = fields.pop("owner", None)
    name = fields.pop("name", None)
    if not fields.get("model_id"):
        if not owner or not name:
            raise ValueError("model card requires model_id, or owner and name to derive it")
        fields["model_id"] = derive_model_id(str(owner), str(name))
    fields.update(
        resource_id=quota.resource_id,
        capacity_site_id=quota.site_id,
        offering_mode=quota.offering_mode,
    )
    return InferenceModelCard.model_validate(fields).model_dump(mode="json", exclude_none=True)
