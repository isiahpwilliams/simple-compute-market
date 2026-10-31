"""The publication guard: only a request-priced rate card is publishable."""

from __future__ import annotations

import pytest

from inference_storefront.rate_card_guard import request_priced_guard
from tests.cards import bound_card

_MAX_JSON_INTEGER = 2**53 - 1


def _card(**rates: int) -> dict:
    card = bound_card()
    card["rate_card"] = {**card["rate_card"], **rates}
    return card


def test_a_request_priced_card_is_publishable() -> None:
    assert request_priced_guard(_card()) is None


@pytest.mark.parametrize(
    "field",
    [
        "prompt_credits_per_million",
        "cached_prompt_credits_per_million",
        "completion_credits_per_million",
        "image_credits_per_unit",
    ],
)
def test_a_non_zero_metered_rate_is_refused_naming_it(field: str) -> None:
    reason = request_priced_guard(_card(**{field: 1}))

    assert reason is not None and f"rate_card.{field}" in reason


def test_the_largest_canonical_json_integer_is_publishable() -> None:
    assert request_priced_guard(_card(request_credits=_MAX_JSON_INTEGER)) is None


@pytest.mark.parametrize("charge", [0, _MAX_JSON_INTEGER + 1])
def test_a_request_charge_outside_the_ledgers_domain_is_refused_naming_it(charge: int) -> None:
    reason = request_priced_guard(_card(request_credits=charge))

    assert reason is not None and "rate_card.request_credits" in reason
