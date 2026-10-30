"""The offering's validation and the gate configuration it projects."""

from __future__ import annotations

from pathlib import Path

import pytest

from arkhai_api_gate import GateConfig, PurchasePointer
from arkhai_api_gateway import GatewayOffering, read_upstream_credential


def _offering(**overrides: object) -> GatewayOffering:
    values: dict[str, object] = {
        "service": "served-model",
        "scope_service": "served-model",
        "scope_resource_id": "quota-1",
        "default_charge": 4,
        "purchase": PurchasePointer(storefront_url="http://storefront"),
        "upstream_base_url": "http://model/v1",
    }
    values.update(overrides)
    return GatewayOffering(**values)  # type: ignore[arg-type]


def test_an_offering_names_a_service() -> None:
    with pytest.raises(ValueError, match="service"):
        _offering(service="")


def test_an_offerings_default_charge_is_non_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _offering(default_charge=-1)
    assert _offering(default_charge=0).default_charge == 0


def test_the_gate_is_configured_from_the_offering() -> None:
    base = GateConfig(service_url="http://authority", authority_label="authority")

    config = _offering().gate_config(base)

    assert config.scope_service == "served-model"
    assert config.scope_resource_id == "quota-1"
    assert config.amount_per_request == 4
    assert config.purchase == PurchasePointer(storefront_url="http://storefront")
    assert config.service_url == "http://authority"


def test_an_upstream_credential_is_read_stripped(tmp_path: Path) -> None:
    path = tmp_path / "credential"
    path.write_text("secret\n", encoding="utf-8")

    assert read_upstream_credential(path) == "secret"


def test_an_empty_upstream_credential_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "credential"
    path.write_text("\n", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        read_upstream_credential(path)
