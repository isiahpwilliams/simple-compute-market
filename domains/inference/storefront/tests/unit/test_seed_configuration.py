"""The development seed publishes one request-priced stub listing over Alkahest alone."""

from __future__ import annotations

import tomllib
from pathlib import Path

from arkhai_inference.listings import derive_model_id

from inference_storefront.model_card import publishable_model_card

_TOML = Path(__file__).resolve().parents[2] / "storefront.inference.toml"


def _settings() -> dict:
    return tomllib.loads(_TOML.read_text(encoding="utf-8"))


def test_the_seed_card_is_publishable_and_request_priced():
    seed = _settings()["seed"]
    card = publishable_model_card(
        seed["model_card"], resource_id=seed["resource_id"], capacity_site_id="default"
    )
    assert card.model_id == derive_model_id("arkhai", "stub-instruct")
    assert card.artifact_ref == "dev://arkhai/stub-instruct"
    assert (card.provenance, card.quantization) == ("self-hosted", "none")
    assert card.rate_card.request_credits == 1
    assert card.endpoint.base_url.startswith("http://inference-gateway:")


def test_the_seed_settles_through_alkahest_alone():
    settlement = _settings()["settlement"]
    assert settlement["priority"] == ["alkahest.v1"]
    assert set(settlement) == {"schema_version", "priority", "alkahest"}
