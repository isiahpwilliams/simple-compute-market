"""What an inference listing's issuance names: the served model, and the terms the key is pinned to."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arkhai_api.issuance import accepted_terms_digest
from arkhai_api_selling.contributions import IssuanceSubject
from arkhai_inference.listings import InferenceModelCard, accepted_terms, coerce_resource_dict


def issuance_projection(listing_resource: Mapping[str, Any]) -> IssuanceSubject:
    """Project the accepted card onto the issuance subject.

    The served model name is the digested service, so a grant binds to what the
    gateway admits in a request's ``model``; the endpoint is not digested.
    """
    card = InferenceModelCard.model_validate(coerce_resource_dict(listing_resource))
    terms = accepted_terms(card)
    return IssuanceSubject(
        service=card.served_model_name,
        resource_id=card.resource_id,
        endpoint=card.endpoint.base_url,
        accepted_terms=terms,
        terms_digest=accepted_terms_digest(terms),
        request_charge=card.rate_card.request_credits,
    )
