"""Usage records and the deterministic charge."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.inference.listings.models import InferenceRateCard
from domains.inference.usage.models import InferenceUsageRecord, derive_charge


def _card(**overrides):
    values = {"prompt_credits_per_million": 500, "completion_credits_per_million": 1500}
    values.update(overrides)
    return InferenceRateCard.model_validate(values)


def _record(**overrides):
    values = {
        "model_id": "meta-llama/llama-3.1-8b-instruct",
        "key_id": "ak_1",
        "request_id": "req-1",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "outcome": "completed",
    }
    values.update(overrides)
    return InferenceUsageRecord.model_validate(values)


def test_cancelled_stream_is_charged_for_produced_tokens_plus_the_request_charge():
    card = _card(completion_credits_per_million=200, request_credits=1)
    record = _record(completion_tokens=400, outcome="cancelled")
    assert derive_charge(record, card) == 2


def test_failed_request_costs_nothing_whatever_it_counted():
    card = _card(request_credits=5)
    record = _record(prompt_tokens=10_000_000, completion_tokens=10_000_000, outcome="failed")
    assert derive_charge(record, card) == 0


@pytest.mark.parametrize(
    "prompt,completion,expected",
    [
        (1_000_000, 0, 500),
        (0, 1_000_000, 1500),
        (1_000_000, 1_000_000, 2000),
        (999_999, 0, 500),
        (1_000_001, 0, 501),
        (1, 0, 1),
    ],
)
def test_exact_million_boundaries_round_up(prompt, completion, expected):
    assert derive_charge(_record(prompt_tokens=prompt, completion_tokens=completion), _card()) == expected


def test_zero_usage_costs_only_the_request_charge():
    assert derive_charge(_record(), _card()) == 0
    assert derive_charge(_record(), _card(request_credits=3)) == 3


def test_cached_tokens_use_the_cached_rate_when_present():
    record = _record(prompt_tokens=1_000_000, cached_prompt_tokens=1_000_000)
    assert derive_charge(record, _card(cached_prompt_credits_per_million=100)) == 600
    assert derive_charge(record, _card()) == 500


def test_images_are_priced_per_unit_outside_the_token_sum():
    record = _record(prompt_tokens=1, image_units=3)
    assert derive_charge(record, _card(image_credits_per_unit=40)) == 121
    assert derive_charge(record, _card()) == 1


def test_charge_is_always_a_non_negative_int():
    for prompt in (0, 1, 999_999, 1_000_000, 123_456_789):
        for completion in (0, 7, 1_000_000):
            charge = derive_charge(_record(prompt_tokens=prompt, completion_tokens=completion), _card())
            assert type(charge) is int
            assert charge >= 0


def test_two_implementations_agree_on_large_values():
    card = _card(prompt_credits_per_million=10**18, completion_credits_per_million=10**18)
    record = _record(prompt_tokens=10**9, completion_tokens=10**9)
    assert derive_charge(record, card) == 2 * 10**21


@pytest.mark.parametrize(
    "field,value",
    [("prompt_tokens", -1), ("prompt_tokens", 1.5), ("prompt_tokens", True), ("outcome", "timeout"), ("request_id", " "), ("extra", 1)],
)
def test_record_rejects_bad_values(field, value):
    with pytest.raises(ValidationError):
        _record(**{field: value})
