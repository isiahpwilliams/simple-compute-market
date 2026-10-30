"""A buyer environment installs the buying libraries and no selling, authority, or payments distribution."""

from __future__ import annotations

import tomllib
from pathlib import Path

LOCK = Path(__file__).resolve().parents[1] / "uv.lock"


def test_a_buyer_environment_installs_no_selling_authority_or_payments_distribution():
    packages = {package["name"] for package in tomllib.loads(LOCK.read_text())["package"]}

    assert {"arkhai-api-buying", "arkhai-api-buying-alkahest", "arkhai-inference-domain"} <= packages
    assert {
        "arkhai-api-buying-arkhai-payments",
        "arkhai-kit-arkhai-payments",
        "arkhai-api-selling",
        "arkhai-api-selling-alkahest",
        "arkhai-api-authority",
        "arkhai-core-storefront",
        "arkhai-kit-capacity-publication",
        "arkhai-kit-storefront",
        "sqlalchemy",
    }.isdisjoint(packages)
