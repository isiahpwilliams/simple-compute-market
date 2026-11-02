"""The request-priced predicate: which rate-card field keeps a card from a fixed per-request charge."""

from __future__ import annotations

import pytest

from arkhai_inference.listings import METERED_RATE_FIELDS, InferenceRateCard, non_request_priced_rate

_MAX_JSON_INTEGER = 2**53 - 1


def _card(**rates: int) -> InferenceRateCard:
    return InferenceRateCard.model_validate(
        {
            "asset": "0x" + "01" * 20,
            "prompt_credits_per_million": 0,
            "completion_credits_per_million": 0,
            "request_credits": 1,
            **rates,
        }
    )


def test_a_request_priced_card_passes() -> None:
    assert non_request_priced_rate(_card()) is None


@pytest.mark.parametrize("field", METERED_RATE_FIELDS)
def test_a_metered_rate_is_named(field: str) -> None:
    assert non_request_priced_rate(_card(**{field: 1})) == field


def test_a_zero_request_charge_is_named() -> None:
    assert non_request_priced_rate(_card(request_credits=0)) == "request_credits"


def test_the_request_charge_is_bounded_by_the_canonical_json_integer_domain() -> None:
    assert non_request_priced_rate(_card(request_credits=_MAX_JSON_INTEGER)) is None
    assert non_request_priced_rate(_card(request_credits=_MAX_JSON_INTEGER + 1)) == "request_credits"
