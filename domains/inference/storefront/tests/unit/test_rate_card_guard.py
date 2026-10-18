"""Only a request-priced rate card is publishable."""

from __future__ import annotations

import pytest
from arkhai_inference.listings import InferenceRateCard

from inference_storefront.rate_card_guard import (
    METERED_RATE_FIELDS,
    RateCardNotPublishable,
    require_request_priced,
)


def _card(**rates: int) -> InferenceRateCard:
    fields = {"prompt_credits_per_million": 0, "completion_credits_per_million": 0, "request_credits": 1}
    return InferenceRateCard(**{**fields, **rates})


def test_a_request_priced_card_passes():
    card = _card()
    assert require_request_priced(card) is card


@pytest.mark.parametrize("field", METERED_RATE_FIELDS)
def test_each_metered_rate_is_refused_by_name(field):
    with pytest.raises(RateCardNotPublishable, match=field):
        require_request_priced(_card(**{field: 7}))
