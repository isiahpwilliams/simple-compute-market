"""The inference storefront's migration command and the startup check it answers.

``inference-storefront-migrate`` applies the family's chain under this
storefront's table prefix to the database its settings name. The command runs
through its entry function with its settings in the loader's environment layer
and no configuration file; no application is started.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from arkhai_api_selling.migrations import (
    IncompatibleStorefrontDatabase,
    baseline_tables,
    require_compatible_storefront_database,
)

from inference_storefront import migrate as migrate_command
from inference_storefront.container import SELLING_CONTRIBUTIONS
from inference_storefront.migrate import CHAIN, TABLE_PREFIX


def _run(monkeypatch, tmp_path: Path, database: Path, *arguments: str) -> int:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-configuration"))
    monkeypatch.setenv("INFERENCE_STOREFRONT_DB_PATH", str(database))
    try:
        migrate_command.main(list(arguments))
    except SystemExit as exit_:
        return int(exit_.code or 0)
    return 0


def test_the_command_builds_the_bundles_tables_and_its_check_passes(tmp_path, monkeypatch):
    path = tmp_path / "storefront.db"

    assert _run(monkeypatch, tmp_path, path, "--check") == 1
    assert not path.exists()
    assert _run(monkeypatch, tmp_path, path) == 0
    assert _run(monkeypatch, tmp_path, path, "--check") == 0

    connection = sqlite3.connect(path)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        connection.close()
    assert SELLING_CONTRIBUTIONS.table_prefix == TABLE_PREFIX
    assert baseline_tables(TABLE_PREFIX) <= tables
    require_compatible_storefront_database(CHAIN, path)


def test_the_startup_check_names_the_command(tmp_path):
    path = tmp_path / "missing" / "storefront.db"

    with pytest.raises(IncompatibleStorefrontDatabase) as refused:
        require_compatible_storefront_database(CHAIN, path)

    assert "`inference-storefront-migrate`" in str(refused.value)
    assert not path.parent.exists()


def test_the_command_resolves_none_of_the_storefronts_configuration():
    """The storefront's configuration module resolves its chains and identity
    when it is imported; the command never imports it."""
    probe = (
        "import sys, inference_storefront.migrate; "
        "sys.exit('inference_storefront.utils.config' in sys.modules)"
    )
    assert subprocess.run([sys.executable, "-c", probe], check=False).returncode == 0
