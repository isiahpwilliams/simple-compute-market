"""Dynaconf configuration and the inference deployment of the family authority.

Precedence: INFERENCE_* env vars, then CONFIG_DIRECTORY's config-<profile>.yml
(per ACTIVE_PROFILES), then config.yml, then settings.toml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from arkhai_api_authority import AuthorityConfig, CapacityProfile
from arkhai_inference.label import INFERENCE_LABEL
from arkhai_inference.listings import INFERENCE_OFFERING_MODE
from dynaconf import Dynaconf
from market_resource_pools import DEFAULT_POOL_ID
from market_resource_pools_contracts import BACKED

_SRC_DIR = Path(__file__).parent
_CONFIG_DIR = Path(os.environ.get("CONFIG_DIRECTORY", str(_SRC_DIR / "config")))

_raw_profiles: str = os.environ.get("ACTIVE_PROFILES", "")
_active_profiles: List[str] = [p.strip() for p in _raw_profiles.split(",") if p.strip()]

_includes: List[str] = []
for _candidate in [_CONFIG_DIR / "config.yml"] + [
    _CONFIG_DIR / f"config-{p}.yml" for p in _active_profiles
]:
    if _candidate.exists():
        _includes.append(str(_candidate))

_dynaconf = Dynaconf(
    settings_file=[str(_SRC_DIR / "settings.toml")],
    includes=_includes,
    envvar_prefix="INFERENCE",
    load_dotenv=True,
    dotenv_files=[".env", ".env.local"],
    envvar_separator="__",
    environments=False,   # profiles are used instead of dynaconf environments
    merge_enabled=True,
)


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
