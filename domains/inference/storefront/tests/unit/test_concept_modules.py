"""The storefront's reference-amount hook reads the whole pinned proposal."""

from __future__ import annotations

from market_core.schemas import RateValue, derive_settlement_option_id
from market_negotiation_runtime import NegotiationTerms

from inference_storefront import negotiation_runtime
from tests.integration.credit_negotiation import model_card

_TOKEN = "0x" + "01" * 20
_ESCROW = "0x" + "11" * 20


def _listing():
    return {
        "listing_id": "L-tok",
        "status": "open",
        "listing_resource": model_card(),
        "accepted_escrows": [{
            "chain_name": "anvil",
            "escrow_address": _ESCROW,
            "literal_fields": {"token": _TOKEN},
            "rates": [{"field": "amount", "per": "credit", "value": "1"}],
        }],
    }


def _rated_option(rate=None):
    rates = [RateValue(field="amount", per="credit", value=rate)] if rate else []
    option = {
        "mechanism": "example.rated.v1",
        "asset": "usd",
        "rates": [r.model_dump(mode="json") for r in rates],
        "params": {},
    }
    option["option_id"] = derive_settlement_option_id(
        mechanism="example.rated.v1", asset="usd", rates=rates, params={}
    )
    return option


def _selecting(option):
    return {"settlement_selection": {
        "mechanism": option["mechanism"], "option_id": option["option_id"],
        "expiration_unix": 2_000_000_000,
    }}


def test_kit_reference_hook_reads_the_whole_pinned_proposal(monkeypatch):
    monkeypatch.setattr(negotiation_runtime, "provision_quantity", lambda _decoded: 3)
    monkeypatch.setattr(negotiation_runtime, "_default_min_price", lambda: None)
    option = _rated_option(rate=1)
    listing = {**_listing(), "settlement_options": [option]}
    terms = NegotiationTerms(decoded={}, wire=None)

    assert negotiation_runtime._reference_amount(
        listing, {}, terms, True, _selecting(option)
    ) == 3
    assert negotiation_runtime._reference_amount(listing, {}, terms, False, None) == 0
