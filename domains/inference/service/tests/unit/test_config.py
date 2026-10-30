"""The inference deployment of the family authority: label, profile, key namespace, distribution."""

from __future__ import annotations

from arkhai_inference.label import INFERENCE_LABEL
from market_resource_pools_contracts import BACKED
from market_resource_pools_contracts.hints import resolve_pool_declarations

from inference_service.config import CAPACITY_PROFILE, ISSUANCE_LABEL, authority_config


def test_the_label_is_the_domain_label_with_the_default_fulfilment_prefix():
    assert ISSUANCE_LABEL is INFERENCE_LABEL
    assert ISSUANCE_LABEL.name == "inference"
    assert ISSUANCE_LABEL.fulfillment_id_prefix == "inference-fulfillment.v1"
    assert ISSUANCE_LABEL.issuance_request_schema == "arkhai.inference.issuance-request.v1"


def test_the_profile_serves_one_inference_pool_backed_by_its_quota():
    assert (
        CAPACITY_PROFILE.offering_mode,
        CAPACITY_PROFILE.pool_provider,
        CAPACITY_PROFILE.pool_id,
        CAPACITY_PROFILE.deliverable_modes,
        CAPACITY_PROFILE.advertisable_modes,
        CAPACITY_PROFILE.backing,
    ) == ("inference", "inference", "default", {"inference"}, {"inference"}, BACKED)


def test_the_pool_policy_tags_resolve_to_the_profiles_declarations():
    tags = CAPACITY_PROFILE.pool_policy_tags()
    assert tags["deliverable_modes"] == ["inference"]
    declarations = resolve_pool_declarations(tags)
    assert declarations.advertisable_modes == frozenset({"inference"})
    assert declarations.backing == BACKED


def test_the_authority_config_names_this_distribution_and_the_ik_prefix():
    assert authority_config.label is ISSUANCE_LABEL
    assert authority_config.profile is CAPACITY_PROFILE
    assert authority_config.distribution == "arkhai-inference-service"
    assert authority_config.key_prefix == "ik"
