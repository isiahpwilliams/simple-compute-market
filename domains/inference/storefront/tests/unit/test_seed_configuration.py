"""The development configuration's seed publishes a request-priced card through the mapping and guard."""

from __future__ import annotations

import tomllib
from pathlib import Path

from arkhai_api_selling.contributions import QuotaSource
from arkhai_api_selling_alkahest.publication import seed_accepted_escrows
from market_alkahest.dev_chain import anvil_address_book_path
from market_config.config_loader import ChainConfig

from inference_storefront.issuance import issuance_projection
from inference_storefront.model_card import publication_mapping
from inference_storefront.rate_card_guard import request_priced_guard

_CONFIG = Path(__file__).resolve().parents[2] / "storefront.inference.toml"


def _seed() -> dict:
    return tomllib.loads(_CONFIG.read_text(encoding="utf-8"))["seed"]


def test_the_seed_card_publishes_under_its_quota_and_passes_the_guard() -> None:
    seed = _seed()
    quota = QuotaSource(site_id="default", resource_id=seed["resource_id"], offering_mode="inference")

    resource = publication_mapping({"model_card": seed["model_card"]}, quota)

    assert request_priced_guard(resource) is None
    subject = issuance_projection(resource)
    assert (subject.service, subject.resource_id, subject.request_charge) == (
        "stub-instruct",
        "stub-instruct-quota",
        1,
    )


def test_the_seed_names_one_alkahest_escrow_at_one_base_unit_per_credit() -> None:
    chains = {
        "anvil": ChainConfig(
            name="anvil",
            rpc_url="http://anvil.test",
            chain_id=31337,
            alkahest_address_config_path=str(anvil_address_book_path()),
        )
    }

    (escrow,) = seed_accepted_escrows(_seed(), chains)

    assert escrow["literal_fields"]["token"] == _seed()["token"]
    assert escrow["rates"][0]["value"] == "1"
