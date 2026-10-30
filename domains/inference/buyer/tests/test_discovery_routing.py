"""Inference-schema discovery: which registries are kept, and queries compiled against the repository's filter spec."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from core_buyer import registry_config
from core_buyer.registry_config import RegistryAuthority, resolve_indexer_urls_for_schema
from market_identity import Ed25519Signer, TrustedIdentitySet
from registry_client import compile_resource_query
from registry_client.models import FilterSpecResponse

from arkhai_inference_buyer.cli import CONTRIBUTIONS

SPEC = Path(__file__).resolve().parents[2] / "registry" / "filter-spec.yaml"
INFERENCE_URL = "http://inference-registry:8080"
# The schema ids the compute and API-credits registries declare in their own specifications.
SCHEMAS = {
    "http://registry:8080": "compute.market",
    "http://apicredits-registry:8080": "api_credits",
    INFERENCE_URL: "inference",
}


class _ScriptedRegistry:
    fetched: list[str] = []

    def __init__(self, base_url: str, **_kwargs) -> None:
        self.base_url = base_url

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def get_filter_spec(self):
        self.fetched.append(self.base_url)
        return SimpleNamespace(schema_id=SCHEMAS[self.base_url])


@pytest.fixture(autouse=True)
def _fresh():
    registry_config.reset_schema_id_cache()
    _ScriptedRegistry.fetched = []
    yield
    registry_config.reset_schema_id_cache()


def _inference_spec() -> FilterSpecResponse:
    return FilterSpecResponse.from_dict({**yaml.safe_load(SPEC.read_text()), "etag": "spec-etag"})


def test_only_the_registry_declaring_inference_is_kept():
    # Deterministic development keys for this test only; never used on any network.
    authorities = {
        url: RegistryAuthority(
            authority=f"registry-{index}",
            principals=TrustedIdentitySet(identities=(Ed25519Signer(bytes([index + 10]) * 32).identity,)),
        )
        for index, url in enumerate(SCHEMAS)
    }
    with (
        patch.object(registry_config, "SyncRegistryClient", _ScriptedRegistry),
        patch.object(registry_config, "resolve_registry_api_keys", return_value={}),
    ):
        kept = resolve_indexer_urls_for_schema(
            CONTRIBUTIONS.schema_id,
            signer=Ed25519Signer(bytes([8]) * 32),
            registry_authorities=authorities,
            override=",".join(SCHEMAS),
        )

    assert sorted(_ScriptedRegistry.fetched) == sorted(SCHEMAS)
    assert kept == [INFERENCE_URL]


def test_the_served_specification_declares_the_plugins_schema():
    assert _inference_spec().schema_id == CONTRIBUTIONS.schema_id


def test_a_model_id_filter_compiles_against_the_inference_specification():
    compiled = compile_resource_query(
        "model_id=arkhai/stub-instruct", filter_spec=_inference_spec(), registry_url=INFERENCE_URL
    )
    assert compiled.schema_id == "inference"
    assert compiled.canonical_query


def test_a_rate_bound_without_its_asset_is_refused_before_sending():
    with pytest.raises(ValueError, match="rate_card_asset"):
        compile_resource_query("prompt_credits<=600", filter_spec=_inference_spec(), registry_url=INFERENCE_URL)
    compiled = compile_resource_query(
        "prompt_credits<=600 rate_card_asset in [0xabc]", filter_spec=_inference_spec(), registry_url=INFERENCE_URL
    )
    assert compiled.canonical_query
