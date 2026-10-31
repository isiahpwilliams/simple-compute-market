"""Alkahest is the plugin's only settlement stage, and no fiat payments distribution is required."""

from __future__ import annotations

from importlib.metadata import requires

import pytest
from market_settlement_runtime.configuration import SettlementConfigurationError
from packaging.requirements import Requirement

from arkhai_inference_buyer.cli import SETTLEMENT
from arkhai_inference_buyer.verification import VerifyingAlkahestStage


def test_the_stage_table_holds_alkahest_alone():
    assert list(SETTLEMENT.stages) == ["alkahest.v1"]
    assert isinstance(SETTLEMENT.stages["alkahest.v1"], VerifyingAlkahestStage)
    assert {item.mechanism_id for item in SETTLEMENT.registry().registrations} == {"alkahest.v1"}


def test_the_plugin_requires_no_payments_distribution():
    names = {Requirement(line).name for line in requires("arkhai-inference-buyer") or ()}
    assert "arkhai-api-buying-alkahest" in names
    assert not {name for name in names if "payments" in name}


def test_a_buyer_configuration_naming_another_mechanism_is_refused():
    with pytest.raises(SettlementConfigurationError, match="arkhai.payments.v1"):
        SETTLEMENT.resolve_policy(
            {"Settlement": {"schema_version": 1, "priority": ["arkhai.payments.v1"]}}
        )
