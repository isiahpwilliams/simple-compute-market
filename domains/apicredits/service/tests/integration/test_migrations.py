"""The API-credit service's migration command, composed over the family authority's chain.

The chain, its refusals, and the startup check are the authority library's and
are tested there. Here: the installed command is this root's, it reads this
service's settings, and it needs none of the application's secrets.

External boundary: file-backed SQLite in a temp directory; the command runs
through its entry point with the service's own settings loader. No application
is started.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from importlib.metadata import entry_points
from pathlib import Path

import pytest
from arkhai_api_authority import authority_chain

from apicredits_service import migrate as migrate_command
from apicredits_service.migrate import CHAIN

COMMAND = "apicredits-service-migrate"


def _schema_and_rows(path: Path) -> tuple[list[tuple], dict[str, list[tuple]]]:
    connection = sqlite3.connect(path)
    try:
        schema = connection.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        tables = [name for kind, name, _ in schema if kind == "table"]
        rows = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
            if table != "schema_migrations"
        }
        return schema, rows
    finally:
        connection.close()


def _recorded(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("SELECT id FROM schema_migrations")]
    finally:
        connection.close()


@pytest.fixture
def command(monkeypatch) -> Callable[..., int]:
    """Run ``apicredits-service-migrate`` with ``configuration`` in the service's
    environment layer; the entry point loads its settings when it runs."""

    def run(database: Path, *arguments: str, **configuration: str) -> int:
        monkeypatch.setenv("APICREDITS_DATABASE_URL", f"sqlite:///{database}")
        for name, value in configuration.items():
            monkeypatch.setenv(f"APICREDITS_{name.upper()}", value)
        try:
            migrate_command.main(list(arguments))
        except SystemExit as exit_:
            return int(exit_.code or 0)
        return 0

    return run


def test_the_chain_is_the_authoritys_named_for_this_service():
    assert CHAIN == authority_chain(service="the API-credit service", command=COMMAND)


def test_the_console_script_is_the_command():
    """The installed ``apicredits-service-migrate`` runs this entry point."""
    (script,) = entry_points(group="console_scripts", name=COMMAND)
    assert script.load() is migrate_command.main


def test_check_passes_only_once_the_command_has_migrated(tmp_path, command):
    path = tmp_path / "credits.db"

    assert command(path, "--check") == 1
    assert not path.exists()
    assert command(path) == 0
    assert command(path) == 0
    assert command(path, "--check") == 0
    assert sorted(_recorded(path)) == sorted(CHAIN.ids)


def test_two_configurations_give_one_schema_and_no_rows(tmp_path, command):
    """Configuration that decides the service's trust and its admin gate
    leaves no trace in what the command migrates."""
    first, second = tmp_path / "first.db", tmp_path / "second.db"

    assert command(first) == 0
    assert command(
        second,
        log_level="debug",
        storefront_admin_key="another-admin-key",
        site_principal="0x0000000000000000000000000000000000000001",
        max_timestamp_skew="5",
    ) == 0

    first_schema, first_rows = _schema_and_rows(first)
    second_schema, second_rows = _schema_and_rows(second)
    assert first_schema == second_schema
    assert sorted(_recorded(first)) == sorted(_recorded(second))
    assert all(rows == [] for rows in (*first_rows.values(), *second_rows.values()))


def test_the_command_runs_without_the_applications_secrets(tmp_path, command):
    """The application refuses to load with its admin-key file unreadable;
    the command, which reads no secret, migrates regardless."""
    path = tmp_path / "credits.db"

    assert command(
        path, storefront_admin_key_file=str(tmp_path / "not-mounted"),
    ) == 0

    assert sorted(_recorded(path)) == sorted(CHAIN.ids)
