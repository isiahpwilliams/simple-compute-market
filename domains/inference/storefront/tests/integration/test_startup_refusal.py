"""A configuration naming a mechanism the storefront does not compose fails startup, naming it."""

from __future__ import annotations

import pytest

from inference_storefront import container
from inference_storefront.startup_refusal import MECHANISM_HEADING, StorefrontStartupError
from tests.integration.conftest import app, replaced, settlement


async def test_a_second_mechanism_fails_startup_before_anything_is_served(storefront):
    served = app()
    with replaced(settlement=settlement("alkahest.v1", "arkhai.payments.v1")):
        with pytest.raises(StorefrontStartupError) as refused:
            async with served.router.lifespan_context(served):
                pass

    assert MECHANISM_HEADING in str(refused.value)
    assert "'arkhai.payments.v1'" in str(refused.value)
    # Refused before the storefront opened its database.
    assert container._sqlite_client is None
    assert not storefront.exists()
