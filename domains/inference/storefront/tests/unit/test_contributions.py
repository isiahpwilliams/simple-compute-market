"""The values inference contributes to the selling library."""

from __future__ import annotations

from arkhai_api_selling.contributions import ConsumptionRule
from arkhai_inference.schema import InferenceListing

from inference_storefront.container import SELLING_CONTRIBUTIONS
from inference_storefront.issuance import issuance_projection
from inference_storefront.materialization import public_result_extension
from inference_storefront.model_card import publication_mapping
from inference_storefront.rate_card_guard import request_priced_guard


def test_the_bundle_carries_inference_values() -> None:
    contributions = SELLING_CONTRIBUTIONS
    assert contributions.label.name == "inference"
    assert contributions.label.fulfillment_id_prefix == "inference-fulfillment.v1"
    assert contributions.kind == "inference.v1"
    assert contributions.offering_mode == "inference"
    assert contributions.contribution_id == "inference"
    assert contributions.table_prefix == "inference"
    assert contributions.listing_schema is InferenceListing
    assert contributions.consumption_rule is ConsumptionRule.FIXED_PER_REQUEST
    assert contributions.refusal_noun == "inference"


def test_the_bundle_composes_the_inference_hooks() -> None:
    contributions = SELLING_CONTRIBUTIONS
    assert contributions.publication_mapping is publication_mapping
    assert contributions.issuance_projection is issuance_projection
    assert contributions.publication_guards == (request_priced_guard,)
    assert contributions.public_result_extension is public_result_extension
    assert contributions.acceptance_hook is None
