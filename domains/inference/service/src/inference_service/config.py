"""The service's settings and the inference deployment of the family authority.

The settings resolve as ``inference_service.settings_source`` describes.
"""

from __future__ import annotations

from arkhai_api_authority import AuthorityConfig, CapacityProfile
from arkhai_inference.label import INFERENCE_LABEL
from arkhai_inference.listings import INFERENCE_OFFERING_MODE
from dynaconf import Dynaconf
from market_resource_pools import DEFAULT_POOL_ID
from market_resource_pools_contracts import BACKED

from inference_service.settings_source import load_settings_source

_dynaconf = load_settings_source()


class Settings:
    """Thin wrapper around dynaconf that adds typed accessors."""

    def __init__(self, source: Dynaconf) -> None:
        self._source = source

    def __getattr__(self, name: str):  # type: ignore[override]
        return getattr(self._source, name)

    @property
    def is_sqlite(self) -> bool:
        return str(self._source.database_url).startswith("sqlite")


settings = Settings(_dynaconf)


# The label is shared with the inference storefront; the profile is the only one
# this service's pool and reservations carry.
ISSUANCE_LABEL = INFERENCE_LABEL

CAPACITY_PROFILE = CapacityProfile(
    offering_mode=INFERENCE_OFFERING_MODE,
    pool_provider="inference",
    pool_id=DEFAULT_POOL_ID,
    pool_label="Default Pool",
    deliverable_modes=frozenset({INFERENCE_OFFERING_MODE}),
    advertisable_modes=frozenset({INFERENCE_OFFERING_MODE}),
    backing=BACKED,
)

authority_config = AuthorityConfig(
    label=ISSUANCE_LABEL,
    profile=CAPACITY_PROFILE,
    database_url=str(settings.database_url),
    distribution="arkhai-inference-service",
    key_prefix="ik",
)
