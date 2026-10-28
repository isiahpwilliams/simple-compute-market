"""Inference listing pricing helpers.

One credit is one base unit of the selected settlement asset, so a listing's
per-credit rate is exactly one and the negotiated scalar amount equals the
purchased quantity. The rate card prices consumption, not purchase.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from market_core.schemas import SettlementOption, SettlementSelection

from arkhai_inference.listings.models import (
    MAX_BASE_UNIT_AMOUNT,
    coerce_resource_dict,
    resource_is_inference,
)

UNIT_RATE = 1


def _settlement_options(order: dict[str, Any]) -> list[SettlementOption]:
    raw = order.get("settlement_options")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return []
    return [SettlementOption.model_validate(entry) for entry in (raw or [])]


def _accepted_escrows(order: dict[str, Any]) -> list[dict[str, Any]]:
    raw = order.get("accepted_escrows")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return []
    return [entry for entry in (raw or []) if isinstance(entry, dict)]


def checked_credit_total(unit_rate: Any, quantity: Any) -> int:
    """Multiply exact integer base units and reject fractions or overflow."""
    if isinstance(unit_rate, bool) or isinstance(quantity, bool):
        raise ValueError("inference rate and quantity must be integers")
    try:
        rate = int(unit_rate)
        count = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("inference rate and quantity must be integers") from exc
    if rate != unit_rate or count != quantity:
        raise ValueError("inference pricing does not admit fractional base units")
    if rate < 0 or count < 1:
        raise ValueError("inference rate must be non-negative and quantity positive")
    total = rate * count
    if total > MAX_BASE_UNIT_AMOUNT:
        raise ValueError("inference quantity-scaled amount exceeds uint256")
    return total


def reference_payment(quantity: Any) -> int:
    """Base units a purchase of ``quantity`` credits settles for."""
    return checked_credit_total(UNIT_RATE, quantity)


def _unit_rate(value: Any, per: Any) -> int:
    if per != "credit":
        raise ValueError("inference settlement rate must be per credit")
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if checked_credit_total(value, 1) != UNIT_RATE:
        raise ValueError("inference settlement rate must be exactly one base unit per credit")
    return UNIT_RATE


def _check_option(option: SettlementOption, asset: str | None) -> int:
    """An option's one amount rate, which must be one per credit, in ``asset``."""
    if asset is not None and option.asset != asset:
        raise ValueError("settlement option asset does not match the rate card's asset")
    amount_rates = [rate for rate in option.rates if rate.field == "amount"]
    if len(amount_rates) != 1:
        raise ValueError("an inference settlement option advertises exactly one amount rate")
    return _unit_rate(amount_rates[0].value, amount_rates[0].per)


def validate_listing_rates(
    settlement_options: Iterable[SettlementOption],
    accepted_escrows: Iterable[dict[str, Any]],
    *,
    asset: str | None = None,
) -> None:
    """Refuse an advertised rate other than one base unit per credit.

    Each settlement option advertises exactly one amount rate, so a listing
    that publishes is one a buyer can select. An escrow states at most one;
    one that states none is priced at the domain's fixed rate. With ``asset``
    given, also refuse an option or escrow token settling in another asset:
    the rate card's integers are base units of exactly one asset, and a
    listing taking payment in two would let a discovery bound read them in
    whichever matched. An escrow that names no token asserts no asset.
    """
    for option in settlement_options:
        _check_option(option, asset)
    for entry in accepted_escrows:
        literal_fields = entry.get("literal_fields")
        token = literal_fields.get("token") if isinstance(literal_fields, dict) else None
        if asset is not None and token is not None and token != asset:
            raise ValueError("accepted escrow token does not match the rate card's asset")
        amount_rates = [
            rate
            for rate in entry.get("rates") or []
            if isinstance(rate, dict) and rate.get("field", "amount") == "amount"
        ]
        if len(amount_rates) > 1:
            raise ValueError("an accepted escrow advertises at most one amount rate")
        for rate in amount_rates:
            _unit_rate(rate.get("value"), rate.get("per", "credit"))


def _card_asset(order: dict[str, Any]) -> str | None:
    rate_card = coerce_resource_dict(order.get("listing_resource")).get("rate_card")
    asset = rate_card.get("asset") if isinstance(rate_card, dict) else None
    return asset if isinstance(asset, str) else None


def selected_unit_price(
    order: dict[str, Any],
    selection: SettlementSelection,
) -> int:
    """Return the selected option's per-credit rate, which must be one."""
    matches = [
        option
        for option in _settlement_options(order)
        if option.option_id == selection.option_id
        and option.mechanism == selection.mechanism
    ]
    if len(matches) != 1:
        raise ValueError("settlement selection does not exact-match one listing option")
    return _check_option(matches[0], _card_asset(order))


def extract_unit_price_from_order(
    order: dict[str, Any],
    *,
    default_min_price: Any = None,
    settlement_selection: SettlementSelection | dict[str, Any] | None = None,
) -> int:
    """The per-credit rate an inference listing settles at: always one.

    Every advertised rate is checked against that constant; a listing that
    advertises no rate is priced at one because the domain fixes it, so a
    configured minimum is admitted only when it is also one.
    """
    if settlement_selection is not None:
        return selected_unit_price(
            order,
            SettlementSelection.model_validate(settlement_selection),
        )

    validate_listing_rates(
        _settlement_options(order),
        _accepted_escrows(order),
        asset=_card_asset(order),
    )

    if default_min_price is not None and str(default_min_price).strip():
        _unit_rate(default_min_price, "credit")
    return UNIT_RATE


def determine_strategy_from_order(order: dict[str, Any] | None) -> str | None:
    """Sellers of prepaid balances always maximize the scalar amount."""
    if not order:
        return None
    if resource_is_inference(order.get("listing_resource")):
        return "maximize"
    return None
