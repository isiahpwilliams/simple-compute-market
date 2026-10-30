"""Key→owner lookup against the inference authority.

The negotiation guard reading it is advisory; issuance re-checks ownership
authoritatively.
"""

from __future__ import annotations

import logging
from typing import Any

from inference_storefront.services.credits_service_client import (
    get_credits_service_client,
)

logger = logging.getLogger(__name__)


async def lookup_key_record(key_id: str) -> dict[str, Any] | None:
    return await get_credits_service_client().get_key(key_id)
