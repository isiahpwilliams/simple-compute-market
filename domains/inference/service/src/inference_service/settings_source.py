"""The service's layered settings, as dynaconf resolves them.

Precedence: INFERENCE_* env vars, then CONFIG_DIRECTORY's config-<profile>.yml
(per ACTIVE_PROFILES), then config.yml, then settings.toml. Every include is
optional.

Loading reads no file a setting names, so the migration command, which needs
only the database location and the log level, loads it without the service's
signing credential mounted.
"""

from __future__ import annotations

import os
from pathlib import Path

from dynaconf import Dynaconf

_SRC_DIR = Path(__file__).parent


def load_settings_source() -> Dynaconf:
    """The settings the environment and configuration files give, read now."""
    config_dir = Path(os.environ.get("CONFIG_DIRECTORY", str(_SRC_DIR / "config")))
    profiles = [
        p.strip() for p in os.environ.get("ACTIVE_PROFILES", "").split(",") if p.strip()
    ]
    includes = [
        str(candidate)
        for candidate in [config_dir / "config.yml"]
        + [config_dir / f"config-{p}.yml" for p in profiles]
        if candidate.exists()
    ]
    return Dynaconf(
        settings_file=[str(_SRC_DIR / "settings.toml")],
        includes=includes,
        envvar_prefix="INFERENCE",
        load_dotenv=True,
        dotenv_files=[".env", ".env.local"],
        envvar_separator="__",
        environments=False,   # profiles are used instead of dynaconf environments
        merge_enabled=True,
    )
