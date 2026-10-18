"""A configuration naming a mechanism other than Alkahest fails the storefront's composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from market_settlement_runtime import SettlementConfigurationError

import inference_storefront.server as server
from inference_storefront.domain_runtime import get_market_domain_contract
from tests._settings_overrides import settings_overrides


def test_a_foreign_settlement_priority_fails_before_any_service_is_built(monkeypatch):
    monkeypatch.setattr(server, "resolve_identity_signer", lambda: SimpleNamespace(identity="seller"))
    monkeypatch.setattr(server, "resolve_admin_identities", lambda: None)
    opened: list[str] = []
    monkeypatch.setattr(server, "get_sqlite_client", lambda **_kwargs: opened.append("db"))

    with settings_overrides(**{"settlement.priority": ["arkhai.payments.v1"]}):
        with pytest.raises(SettlementConfigurationError, match="arkhai.payments.v1"):
            server._build_inference_services(get_market_domain_contract())

    assert opened == []
