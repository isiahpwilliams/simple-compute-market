"""The gateway's settings, and the gate configuration the offering completes."""

from __future__ import annotations

from pathlib import Path

import pytest
from arkhai_api_gate import PurchasePointer

from inference_gateway_service.config import PREFIX, GatewaySettings, gate_config
from inference_gateway_service.offering import project
from tests.cards import QUOTA, SERVED_MODEL, settings, summary

ENVIRONMENT = {
    "STOREFRONT_URL": "http://storefront.test/",
    "RESOURCE_ID": QUOTA,
    "SERVED_MODEL_NAME": SERVED_MODEL,
    "UPSTREAM_BASE_URL": "http://model.test/v1",
}


def _environ(**overrides: str) -> dict[str, str]:
    return {PREFIX + name: value for name, value in {**ENVIRONMENT, **overrides}.items()}


def test_the_settings_read_the_gateway_prefix():
    read = GatewaySettings.from_env(_environ(LISTING_ID="lst-9", UPSTREAM_CREDENTIAL_FILE="/run/secrets/arkhai/upstream"))

    assert (read.storefront_url, read.resource_id, read.served_model_name) == (
        "http://storefront.test", QUOTA, SERVED_MODEL,
    )
    assert (read.listing_id, read.upstream_credential_file) == ("lst-9", Path("/run/secrets/arkhai/upstream"))


def test_a_missing_setting_is_named():
    environ = _environ()
    del environ[PREFIX + "RESOURCE_ID"]

    with pytest.raises(ValueError, match=PREFIX + "RESOURCE_ID"):
        GatewaySettings.from_env(environ)


def test_the_gate_takes_its_scope_and_charge_from_the_offering(monkeypatch):
    monkeypatch.setenv(PREFIX + "SERVICE_URL", "http://authority.test")
    monkeypatch.setenv(PREFIX + "AMOUNT_PER_REQUEST", "99")

    configured = project(summary(), settings()).gate_config(gate_config())

    assert configured.service_url == "http://authority.test"
    assert (configured.scope_service, configured.scope_resource_id) == (SERVED_MODEL, QUOTA)
    assert configured.amount_per_request == 3
    assert configured.purchase == PurchasePointer(
        service_name=SERVED_MODEL, listing_id="lst-1",
        storefront_url="http://storefront.test", registry_url="http://registry.test",
    )
