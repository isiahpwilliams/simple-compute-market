"""Alkahest is the only mechanism the storefront composes, and its wheel installs no other."""

from __future__ import annotations

from importlib.metadata import requires

from market_alkahest import ALKAHEST_MECHANISM_ID
from packaging.requirements import Requirement

from inference_storefront.container import ALKAHEST_STAGE, SELLER_STAGES


def test_the_seller_stage_table_holds_alkahest_alone() -> None:
    assert dict(SELLER_STAGES) == {ALKAHEST_MECHANISM_ID: ALKAHEST_STAGE}


def test_the_wheel_requires_no_fiat_payments_distribution() -> None:
    names = {Requirement(line).name for line in requires("arkhai-inference-storefront") or ()}

    assert "arkhai-api-selling-alkahest" in names
    assert not {name for name in names if "arkhai-payments" in name}
