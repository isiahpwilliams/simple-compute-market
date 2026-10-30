"""The inference buyer CLI contributes a validated market-domain contract."""

from __future__ import annotations

from core_buyer.plugins import discover_domains
from market_core import DomainCapability, MarketDomainContract
from typer.testing import CliRunner

from arkhai_inference_buyer.cli import CONTRIBUTIONS, app, domain

runner = CliRunner()


def test_entry_point_discovery_loads_the_inference_contract_once():
    identities = [item.identity for item in discover_domains()]
    assert identities.count("inference.v1") == 1


def test_domain_is_a_buyer_contract_under_the_inference_schema():
    assert isinstance(domain, MarketDomainContract)
    assert domain.identity == "inference.v1"
    assert domain.has_capability(DomainCapability.BUYER)
    assert not domain.has_capability(DomainCapability.COMPUTE_PROVISIONING)
    assert domain.buyer.identity_injection_contract == "core.resolved-buyer-identity.v1"
    assert CONTRIBUTIONS.schema_id == "inference"


def test_assembled_app_exposes_the_inference_group_and_its_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "inference" in result.output
    result = runner.invoke(app, ["inference", "--help"])
    assert result.exit_code == 0, result.output
    for name in ("buy", "negotiate", "settle", "settlement", "listing"):
        assert name in result.output, f"missing inference command {name!r}"
    for group, sub in (("listing", "list"), ("listing", "show"), ("settlement", "status")):
        result = runner.invoke(app, ["inference", group, "--help"])
        assert result.exit_code == 0, result.output
        assert sub in result.output


def test_buy_surface_has_quantity_key_and_resource_flags():
    result = runner.invoke(app, ["inference", "buy", "--help"])
    assert result.exit_code == 0, result.output
    for flag in ("--quantity", "--new-key", "--key-id", "--resource", "--max-price"):
        assert flag in result.output, f"missing flag {flag!r}"


def test_version_reports_the_domain_contract():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "inference.v1" in result.output
