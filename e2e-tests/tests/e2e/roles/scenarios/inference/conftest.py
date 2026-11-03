"""Settings and the buyer shared by the inference lane's scenario."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from market_identity import IdentityScheme

from e2e_harness.settings import settings
from tests.e2e.roles.buyer_cli import (
    BuyerCli,
    _alkahest_addresses_path,
    _toml_quote,
    create_profiled_buyer_cli,
)

log = logging.getLogger(__name__)


def lane_setting(name: str) -> str:
    """One inference lane setting, failing the scenario when it is absent.

    The lane supplies its own configuration, so a missing value is a broken
    lane, not a scenario to skip.
    """
    value = str(settings.get(name, "") or "").strip()
    if not value:
        pytest.fail(f"inference lane setting {name} is not configured")
    return value


def _registry_pin(prefix: str) -> tuple[str, dict[str, Any]]:
    url = lane_setting(f"INFERENCE.{prefix}_URL").rstrip("/")
    return url, {
        "authority": lane_setting(f"INFERENCE.{prefix}_AUTHORITY_ID"),
        "identities": [
            {
                "scheme": lane_setting(f"INFERENCE.{prefix}_SCHEME"),
                "identifier": lane_setting(f"INFERENCE.{prefix}_IDENTIFIER"),
            }
        ],
    }


@pytest.fixture(scope="module")
def inference_buyer_cli(buyer_cli_binary, tmp_path_factory) -> BuyerCli:
    """A buyer pinning all three of the lane's registries.

    Discovery is authenticated in both directions, so every registry the buyer
    reads is pinned, though the schema filter routes inference discovery to one.
    """
    rpc_url = lane_setting("BUYER.CHAIN_RPC_URL")
    if rpc_url.startswith("http://"):
        rpc_url = "ws://" + rpc_url[len("http://"):]
    alkahest_path = _alkahest_addresses_path()
    if not alkahest_path:
        pytest.fail("Could not locate alkahest_anvil_addresses.json")
    pins = [_registry_pin(p) for p in ("COMPUTE_REGISTRY", "API_CREDITS_REGISTRY", "REGISTRY")]
    log.info("[inference_buyer_cli] registries=%s rpc=%s", [url for url, _ in pins], rpc_url)
    yield create_profiled_buyer_cli(
        binary=buyer_cli_binary,
        base=tmp_path_factory.mktemp("inference_buyer_cli"),
        domain_identity="inference.v1",
        marketplace_scheme=IdentityScheme.EIP191,
        marketplace_credential=lane_setting("BUYER.MARKETPLACE_CREDENTIAL"),
        registries=[url for url, _ in pins],
        registry_authorities=dict(pins),
        credential_variable="ARKHAI_E2E_BUYER_MARKETPLACE_CREDENTIAL",
        toml_sections=(
            "[wallet]",
            f"address = {_toml_quote(lane_setting('BUYER.WALLET_ADDRESS'))}",
            f"private_key = {_toml_quote(lane_setting('BUYER.PRIVATE_KEY'))}",
            "",
            "[chains.anvil]",
            f"rpc_url = {_toml_quote(rpc_url)}",
            f"alkahest_address_config_path = {_toml_quote(alkahest_path)}",
            "",
            "[Settlement]",
            "schema_version = 1",
            'priority = ["alkahest.v1"]',
            "",
            "[Settlement.alkahest]",
            "enabled = true",
            f"address_config_path = {_toml_quote(alkahest_path)}",
            "oracle_gated = false",
            "trusted_oracle_addresses = []",
            "interruptible = false",
            "interruptible_oracle_addresses = []",
            "",
        ),
    )
