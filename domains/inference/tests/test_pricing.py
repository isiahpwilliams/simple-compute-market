"""Inference purchase pricing: one credit is one base unit."""

from __future__ import annotations

import json

import pytest
from market_core.schemas import RateValue, SettlementSelection, derive_settlement_option_id

from domains.inference.listings.models import INFERENCE_KIND
from domains.inference.listings.pricing import (
    UNIT_RATE,
    checked_credit_total,
    determine_strategy_from_order,
    extract_unit_price_from_order,
    reference_payment,
    selected_unit_price,
)

_ASSET = "0x" + "01" * 20


def _option(value=1, per="credit", field="amount"):
    rates = [RateValue(field=field, per=per, value=value)]
    return {
        "option_id": derive_settlement_option_id(
            mechanism="alkahest.v1", asset=_ASSET, rates=rates, params={}
        ),
        "mechanism": "alkahest.v1",
        "asset": _ASSET,
        "rates": [rate.model_dump(mode="json") for rate in rates],
        "params": {},
    }


def _order(*options, **extra):
    order = {
        "listing_id": "listing-1",
        "listing_resource": {"kind": INFERENCE_KIND, "model_id": "meta-llama/llama-3.1-8b-instruct"},
        "settlement_options": list(options),
    }
    order.update(extra)
    return order


def _selection(option):
    return SettlementSelection(
        mechanism=option["mechanism"], option_id=option["option_id"], expiration_unix=2_000_000_000
    )


def test_reference_payment_equals_quantity():
    assert reference_payment(1) == 1
    assert reference_payment(2_000_000) == 2_000_000
    assert checked_credit_total(UNIT_RATE, 7) == 7


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "5"])
def test_reference_payment_rejects_non_positive_integers(quantity):
    with pytest.raises(ValueError):
        reference_payment(quantity)


def test_reference_payment_rejects_overflow():
    with pytest.raises(ValueError):
        reference_payment(2**256)


def test_selected_option_at_unit_rate_prices_at_one():
    option = _option()
    assert selected_unit_price(_order(option), _selection(option)) == 1


@pytest.mark.parametrize("value", [0, 2, 100])
def test_selected_option_at_non_unit_rate_is_rejected(value):
    option = _option(value=value)
    with pytest.raises(ValueError, match="exactly one"):
        selected_unit_price(_order(option), _selection(option))


@pytest.mark.parametrize("per", ["hour", "token", "request"])
def test_selected_option_not_per_credit_is_rejected(per):
    option = _option(per=per)
    with pytest.raises(ValueError, match="per credit"):
        selected_unit_price(_order(option), _selection(option))


def test_selection_must_match_exactly_one_option():
    option = _option()
    other = _option(value=1, per="credit")
    other["mechanism"] = "fiat.stripe.v1"
    with pytest.raises(ValueError, match="exact-match"):
        selected_unit_price(_order(option), _selection(other))


def test_extract_via_selection_delegates():
    option = _option()
    assert extract_unit_price_from_order(_order(option), settlement_selection=_selection(option)) == 1
    assert (
        extract_unit_price_from_order(
            _order(option), settlement_selection=_selection(option).model_dump(mode="json")
        )
        == 1
    )


def test_extract_checks_every_advertised_rate():
    assert extract_unit_price_from_order(_order(_option())) == 1
    with pytest.raises(ValueError, match="exactly one"):
        extract_unit_price_from_order(_order(_option(), _option(value=3)))


def test_extract_accepts_json_text_columns():
    order = _order(_option())
    order["settlement_options"] = json.dumps(order["settlement_options"])
    assert extract_unit_price_from_order(order) == 1


def test_extract_checks_legacy_escrow_rates():
    escrow = {"chain_name": "anvil", "escrow_address": "0x" + "11" * 20, "rates": [{"field": "amount", "per": "credit", "value": "1"}]}
    assert extract_unit_price_from_order(_order(accepted_escrows=[escrow])) == 1
    escrow["rates"][0]["value"] = "2"
    with pytest.raises(ValueError, match="exactly one"):
        extract_unit_price_from_order(_order(accepted_escrows=[escrow]))


def test_listing_with_no_advertised_rate_prices_at_one():
    assert extract_unit_price_from_order(_order()) == 1
    assert extract_unit_price_from_order(_order(), default_min_price="1") == 1
    assert extract_unit_price_from_order(_order(), default_min_price=1) == 1


def test_configured_minimum_other_than_one_is_rejected():
    with pytest.raises(ValueError, match="exactly one"):
        extract_unit_price_from_order(_order(), default_min_price="5")


def test_rate_card_has_no_effect_on_purchase_price():
    option = _option()
    order = _order(option)
    order["listing_resource"]["rate_card"] = {
        "prompt_credits_per_million": 500_000,
        "completion_credits_per_million": 1_500_000,
    }
    assert selected_unit_price(order, _selection(option)) == 1
    assert reference_payment(10) == 10


def test_strategy_is_maximize_for_inference_only():
    assert determine_strategy_from_order(_order()) == "maximize"
    assert determine_strategy_from_order({"listing_resource": {"kind": "api_credits.v1"}}) is None
    assert determine_strategy_from_order(None) is None
