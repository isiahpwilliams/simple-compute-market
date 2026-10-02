"""Inference listing pricing helpers.

One credit is one base unit of the selected settlement asset, so a listing's
per-credit rate is exactly one and the negotiated scalar amount equals the
purchased quantity. The rate card prices consumption, not purchase.
"""

from __future__ import annotations

import json
from typing import Any

from market_core.schemas import SettlementOption, SettlementSelection

from arkhai_inference.listings.models import resource_is_inference

UNIT_RATE = 1
_MAX_BASE_UNIT_AMOUNT = 2**256 - 1


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
    if total > _MAX_BASE_UNIT_AMOUNT:
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
    amount_rates = [rate for rate in matches[0].rates if rate.field == "amount"]
    if len(amount_rates) != 1:
        raise ValueError("selected inference option requires one amount rate")
    return _unit_rate(amount_rates[0].value, amount_rates[0].per)


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

    for option in _settlement_options(order):
        for rate in option.rates:
            if rate.field == "amount":
                _unit_rate(rate.value, rate.per)
    for entry in _accepted_escrows(order):
        for rate in entry.get("rates") or []:
            if isinstance(rate, dict) and rate.get("field", "amount") == "amount":
                _unit_rate(rate.get("value"), rate.get("per", "credit"))

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
