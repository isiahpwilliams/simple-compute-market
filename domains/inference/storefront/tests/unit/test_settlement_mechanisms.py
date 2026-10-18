"""Alkahest is the only mechanism the storefront registers."""

from __future__ import annotations

import pytest
from market_settlement_runtime import SettlementConfigurationError

from inference_storefront.settlement_composition import (
    SELLER_STAGES,
    build_storefront_settlement_registry,
)


def test_the_seller_table_holds_alkahest_alone():
    assert set(SELLER_STAGES) == {"alkahest.v1"}


def test_a_configuration_naming_another_mechanism_is_refused_by_name():
    registry = build_storefront_settlement_registry()
    with pytest.raises(SettlementConfigurationError, match="arkhai.payments.v1"):
        registry.resolve(
            {"schema_version": 1, "priority": ["arkhai.payments.v1"], "alkahest": {"enabled": True}},
            role="seller",
        )
