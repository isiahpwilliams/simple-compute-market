"""`market inference settle --from` reports a storefront scope refusal once and does not retry."""

from __future__ import annotations

import base64
import json
import uuid
from types import SimpleNamespace

import arkhai_api_buying.common as common
import arkhai_api_buying.commands as commands
import arkhai_api_buying.stages as stages
import arkhai_api_buying_alkahest.stage as alkahest_stage
import pytest
from core_buyer.buyer_config import ResolvedBuyerIdentity
from market_core.schemas import Agreement, SettlementOption, derive_settlement_option_id
from market_identity import REQUEST_PROTOCOL, Eip191Signer, TrustedIdentitySet
from typer.testing import CliRunner

from arkhai_inference_buyer.cli import app

_PROPOSAL = {
    "chain_name": "anvil",
    "escrow_address": "0x" + "cd" * 20,
    "fields": {"amount": 300, "token": "0x" + "ab" * 20},
    "literal_fields": {"token": "0x" + "ab" * 20},
    "rates": [],
    "demands": [],
    "expiration_unix": 1_800_000_000,
}
# Deterministic development keys for these tests only; never used on any network.
_SIGNER = Eip191Signer(bytes.fromhex("11" * 32))
_SELLER_SIGNER = Eip191Signer(bytes.fromhex("22" * 32))
_PROFILE_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
_IDENTITY = ResolvedBuyerIdentity(
    profile_id=_PROFILE_ID, principal=_SIGNER.identity, signer=_SIGNER, source="recovery",
)
_REFUSAL = "key_out_of_scope"


def _event(event: str, **fields) -> dict:
    if fields.get("status") == "agreed":
        params = {"accepted_escrow": dict(_PROPOSAL)}
        option = SettlementOption(
            option_id=derive_settlement_option_id(mechanism="alkahest.v1", asset="token", rates=[], params=params),
            mechanism="alkahest.v1", asset="token", rates=[], params=params,
        )
        agreement = Agreement(
            negotiation_id=fields["negotiation_id"], listing_id="lst-1", listing_hash="0" * 64,
            buyer=_SIGNER.identity.model_dump(mode="json"), seller=_SELLER_SIGNER.identity.model_dump(mode="json"),
            settlement=option, amount=300, asset="token", duration_seconds=0,
            start_utc="2025-01-01T00:00:00Z", accepted_at="2025-01-01T00:00:00Z",
        )
        fields["agreement"] = agreement.model_dump(mode="json")
        fields["agreement_bytes"] = base64.b64encode(agreement.model_dump_json().encode()).decode()
        fields["settlement_selection"] = {
            "mechanism": option.mechanism, "option_id": option.option_id, "expiration_unix": 1_800_000_000,
        }
    return {
        "event": event,
        "run_id": "run-topup-1",
        "log_version": 3,
        "signature_protocol": REQUEST_PROTOCOL,
        "signature_version": 2,
        "buyer_profile_id": str(_PROFILE_ID),
        "buyer_principal": _SIGNER.identity.model_dump(mode="json"),
        **fields,
    }


@pytest.fixture
def agreed_top_up(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    runs = tmp_path / "arkhai" / "buy-runs"
    runs.mkdir(parents=True)
    events = [
        _event(
            "run_started", command="market inference negotiate", seller_url="http://seller:8002",
            listing_id="lst-1", quantity=100, key_mode="existing", key_id="ik_existing",
            chain_name="anvil", publisher_id="publisher-1",
            source_registry_url="http://registry:8080", source_registry_authority="registry-1",
        ),
        _event(
            "run_ended", status="agreed",
            publisher_principals=TrustedIdentitySet(identities=(_SELLER_SIGNER.identity,)).model_dump(mode="json"),
            negotiation_id="neg-1", agreed_amount=300, accepted_escrow_proposal=_PROPOSAL,
        ),
        _event("escrow_created", escrow_uid="0x" + "ee" * 32, chain_name="anvil"),
    ]
    (runs / "run-topup-1.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")

    chain = SimpleNamespace(name="anvil", rpc_url="http://anvil:8545", chain_id=31337, alkahest_address_config_path=None)
    trust = TrustedIdentitySet(identities=(_SELLER_SIGNER.identity,))
    monkeypatch.setattr(alkahest_stage, "chain_by_name", lambda _name: chain)
    monkeypatch.setattr(alkahest_stage, "resolve_buyer_wallet", lambda: ("0x" + "cc" * 20, "0x" + "11" * 32))
    monkeypatch.setattr(common, "make_run_publisher_principals_refresh", lambda *_a, **_k: lambda *_b: trust)
    monkeypatch.setattr(common, "resolve_indexer_urls", lambda: ["http://registry:8080"])
    monkeypatch.setattr(common, "resolve_registry_authorities", lambda _urls: {"http://registry:8080": object()})
    monkeypatch.setattr(common, "resolve_registry_api_keys", lambda: {})
    monkeypatch.setattr(common, "resolve_discovery_timeout", lambda: 5.0)
    monkeypatch.setattr(stages, "make_publisher_trust_resolver", lambda **_kw: lambda: trust)
    monkeypatch.setattr(commands.common, "resolve_recovery_buyer_identity", lambda _run: _IDENTITY)
    return "run-topup-1"


def _script_seller(monkeypatch, terminal: dict) -> dict[str, int]:
    calls = {"submit": 0, "wait": 0}

    def submit(**_kw):
        calls["submit"] += 1
        return {"status": "queued"}

    def wait(**_kw):
        calls["wait"] += 1
        return dict(terminal)

    monkeypatch.setattr(alkahest_stage, "submit_settlement_request", submit)
    monkeypatch.setattr(alkahest_stage, "wait_for_settlement", wait)
    return calls


def test_a_top_up_refused_out_of_scope_is_reported_once_and_not_retried(agreed_top_up, monkeypatch):
    calls = _script_seller(monkeypatch, {"status": "failed", "reason": _REFUSAL})

    result = CliRunner().invoke(app, ["inference", "settle", "--from", agreed_top_up])

    assert result.exit_code == 7, (result.output, result.exception)
    assert result.output.count(_REFUSAL) == 1
    assert calls == {"submit": 1, "wait": 1}


def test_a_completed_purchase_shows_the_key_and_the_base_url(agreed_top_up, monkeypatch):
    credentials = {"key_id": "ik_existing", "base_url": "http://inference-gateway:8105/v1", "balance": 400}
    _script_seller(monkeypatch, {"status": "ready", "fulfillment_uid": "f-1", "tenant_credentials": credentials})

    result = CliRunner().invoke(app, ["inference", "settle", "--from", agreed_top_up])

    assert result.exit_code == 0, (result.output, result.exception)
    assert "ik_existing" in result.output
    assert "http://inference-gateway:8105/v1" in result.output
