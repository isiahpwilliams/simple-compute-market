"""Ordered SQLite migrations: schema_migrations tracking, idempotency,
and adoption of a database that predates this migration system.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from arkhai_api_authority.database import create_db_engine, run_migrations
from arkhai_api_authority.migrations import (
    SchemaDriftError,
    apply_schema_migrations,
    check_schema_version,
)
from arkhai_api_authority import migrations as migrations_module
from arkhai_api_authority.models import Base
from market_resource_pools.db import Base as PoolsBase
from market_site.db import Base as SiteBase


def _sqlite_memory_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


class TestRunMigrationsFreshBootstrap:
    def test_creates_every_expected_table(self):
        engine = _sqlite_memory_engine()
        run_migrations(engine)

        tables = set(inspect(engine).get_table_names())
        columns = {
            column["name"] for column in inspect(engine).get_columns("credit_grants")
        }
        assert columns == set(Base.metadata.tables["credit_grants"].columns.keys())
        assert "negotiation_id" in columns
        assert {"escrow_uid", "obligation_ref", "mechanism"}.isdisjoint(columns)
        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspect(engine).get_unique_constraints("credit_grants")
        }
        assert {("fulfillment_id",), ("negotiation_id",)} <= unique_columns
        assert {
            "api_keys",
            "credit_grants",
            "consumption_events",
            "schema_migrations",
            "capacity_buckets",
            "capacity_reservations",
        } <= tables

    def test_records_baseline_migration(self):
        # A fresh bootstrap adopts the existing create_all schema into
        # durable migration versioning.
        engine = _sqlite_memory_engine()
        run_migrations(engine)

        with engine.begin() as connection:
            rows = connection.execute(
                text("SELECT id FROM schema_migrations")
            ).fetchall()
        assert rows == [
            ("20260731_001_apicredits_schema_baseline",),
            ("20260811_002_canonical_owner_principals",),
            ("20260815_003_fulfillment_grants",),
            ("20260922_004_pool_advertisement_and_backing",),
            ("20261005_005_reservation_release_requested_at",),
            ("20261030_006_grant_terms",),
        ]

    def test_a_reservation_table_from_before_release_timing_gains_the_column(self):
        """The site ledger this service composes records when a reservation
        began releasing; a table created before that column existed gains it."""
        engine = _sqlite_memory_engine()
        run_migrations(engine)
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE capacity_reservations DROP COLUMN release_requested_at")
            )
            connection.execute(
                text(
                    "DELETE FROM schema_migrations "
                    "WHERE id = '20261005_005_reservation_release_requested_at'"
                )
            )

        run_migrations(engine)

        with engine.begin() as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    text("PRAGMA table_info(capacity_reservations)")
                ).fetchall()
            }
        assert "release_requested_at" in columns


class TestRunMigrationsIsIdempotent:
    def test_running_twice_does_not_error_or_duplicate_bookkeeping(self):
        engine = _sqlite_memory_engine()
        run_migrations(engine)
        run_migrations(engine)  # must not raise

        with engine.begin() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM schema_migrations")
            ).scalar()
        assert count == 6


class TestAdoptingAPreCreateAllOnlyDatabase:
    """A database created by a create_all()-only startup (no
    schema_migrations table at all) must be adopted cleanly -- not treated
    as corrupt, and not silently skipped in a way that leaves it unable to
    receive future migrations.
    """

    def test_adopts_a_database_with_no_schema_migrations_table(self):
        engine = _sqlite_memory_engine()
        # Simulate the pre-migration-system startup path directly,
        # bypassing run_migrations entirely.
        Base.metadata.create_all(bind=engine)
        from market_site.db import Base as SiteBase

        SiteBase.metadata.create_all(bind=engine)

        assert "schema_migrations" not in set(inspect(engine).get_table_names())

        # The real startup path, run against this old-shaped database.
        run_migrations(engine)

        tables = set(inspect(engine).get_table_names())
        assert "schema_migrations" in tables
        assert "api_keys" in tables  # pre-existing table untouched, not recreated

    def test_adopts_a_database_with_existing_data_without_touching_it(self):
        engine = _sqlite_memory_engine()
        Base.metadata.create_all(bind=engine)
        from market_site.db import Base as SiteBase

        SiteBase.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO api_keys "
                    "(key_id, secret_hash, status, balance, created_at, updated_at) "
                    "VALUES ('k1', 'hash1', 'active', 42, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )

        run_migrations(engine)

        with engine.begin() as connection:
            row = connection.execute(
                text("SELECT balance FROM api_keys WHERE key_id = 'k1'")
            ).fetchone()
        assert row is not None
        assert row[0] == 42

    def test_migrates_wallet_owner_to_canonical_eip191_principal(self):
        engine = _sqlite_memory_engine()
        Base.metadata.create_all(bind=engine)
        from market_site.db import Base as SiteBase

        SiteBase.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO api_keys "
                    "(key_id, secret_hash, owner_scheme, owner_id, status, balance, "
                    "created_at, updated_at) VALUES "
                    "('k1', 'hash1', 'wallet', "
                    "'0xABCDEF0000000000000000000000000000000001', "
                    "'active', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )

        run_migrations(engine)

        with engine.begin() as connection:
            row = connection.execute(
                text("SELECT owner_scheme, owner_id FROM api_keys WHERE key_id = 'k1'")
            ).one()
        assert row == (
            "eip191",
            "0xabcdef0000000000000000000000000000000001",
        )

    def test_incompatible_grant_schema_requires_explicit_reset(self):
        engine = _sqlite_memory_engine()
        run_migrations(engine)
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE credit_grants ADD COLUMN escrow_uid VARCHAR")
            )

        for check in (run_migrations, check_schema_version):
            with pytest.raises(SchemaDriftError, match="explicitly reset"):
                check(engine)
        assert "escrow_uid" in {
            column["name"] for column in inspect(engine).get_columns("credit_grants")
        }

    def test_malformed_owner_rolls_back_principal_migration(self):
        engine = _sqlite_memory_engine()
        Base.metadata.create_all(bind=engine)
        from market_site.db import Base as SiteBase

        SiteBase.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO api_keys "
                    "(key_id, secret_hash, owner_scheme, owner_id, status, balance, "
                    "created_at, updated_at) VALUES "
                    "('good', 'hash1', 'wallet', "
                    "'0xABCDEF0000000000000000000000000000000001', "
                    "'active', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
                    "('bad', 'hash2', 'wallet', 'not-an-address', "
                    "'active', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )

        with pytest.raises(SchemaDriftError):
            run_migrations(engine)

        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT key_id, owner_scheme, owner_id FROM api_keys ORDER BY key_id"
                )
            ).fetchall()
        assert rows == [
            ("bad", "wallet", "not-an-address"),
            (
                "good",
                "wallet",
                "0xABCDEF0000000000000000000000000000000001",
            ),
        ]


class TestCheckSchemaVersion:
    """The fail-fast check a deployment with a separate migration step runs
    before its service starts (see migrations.py's module docstring).
    """

    def test_passes_after_baseline_is_applied(self):
        engine = _sqlite_memory_engine()
        Base.metadata.create_all(bind=engine)
        from market_site.db import Base as SiteBase

        SiteBase.metadata.create_all(bind=engine)
        apply_schema_migrations(engine)
        check_schema_version(engine)

    def test_raises_when_schema_migrations_table_is_entirely_missing(self):
        engine = _sqlite_memory_engine()
        Base.metadata.create_all(bind=engine)
        # Only meaningful once _MIGRATIONS is non-empty; document the
        # intended behavior now so it's exercised the moment a real
        # migration is added, rather than discovered broken then.
        import arkhai_api_authority.migrations as migrations_module

        original = migrations_module._MIGRATIONS
        migrations_module._MIGRATIONS = (
            migrations_module.Migration("00000000_placeholder", lambda engine: None),
        )
        try:
            with pytest.raises(SchemaDriftError):
                check_schema_version(engine)
        finally:
            migrations_module._MIGRATIONS = original


class TestCreateDbEngineIsSqliteOnly:
    def test_raises_for_a_non_sqlite_url(self):
        with pytest.raises(ValueError):
            create_db_engine("postgresql://user:pass@host/db", is_sqlite=False)

    def test_accepts_a_sqlite_url(self):
        engine = create_db_engine("sqlite:///:memory:", is_sqlite=True)
        assert engine is not None


def test_failed_migration_is_not_recorded_and_prior_success_is_preserved(monkeypatch):
    import arkhai_api_authority.migrations as migrations_module

    engine = _sqlite_memory_engine()
    Base.metadata.create_all(bind=engine)
    from market_site.db import Base as SiteBase

    SiteBase.metadata.create_all(bind=engine)

    calls: list[str] = []

    def first(_engine):
        calls.append("first")

    def fail(_engine):
        calls.append("fail")
        raise RuntimeError("boom")

    monkeypatch.setattr(
        migrations_module,
        "_MIGRATIONS",
        (
            migrations_module.Migration("001", first),
            migrations_module.Migration("002", fail),
        ),
    )

    with pytest.raises(RuntimeError, match="boom"):
        migrations_module.apply_schema_migrations(engine)

    with engine.begin() as connection:
        rows = connection.execute(
            text("SELECT id FROM schema_migrations ORDER BY id")
        ).fetchall()

    assert rows == [("001",)]
    with pytest.raises(SchemaDriftError):
        migrations_module.check_schema_version(engine)
    assert calls == ["first", "fail"]


class TestGrantTermsUpgrade:
    """A database at the previous chain head gains ``grant_terms`` and keeps its grants unpinned."""

    def _previous_head(self, monkeypatch):
        engine = _sqlite_memory_engine()
        previous = tuple(m for m in migrations_module._MIGRATIONS if m.id != "20261030_006_grant_terms")
        Base.metadata.create_all(
            bind=engine, tables=[t for t in Base.metadata.sorted_tables if t.name != "grant_terms"]
        )
        PoolsBase.metadata.create_all(bind=engine)
        SiteBase.metadata.create_all(bind=engine)
        with monkeypatch.context() as patched:
            patched.setattr(migrations_module, "_MIGRATIONS", previous)
            apply_schema_migrations(engine)
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO api_keys (key_id, secret_hash, status, balance, created_at, updated_at) "
                "VALUES ('ak_old', 'hash', 'active', 5, '2026-10-01', '2026-10-01')"
            ))
            connection.execute(text(
                "INSERT INTO credit_grants (key_id, fulfillment_id, service, resource_id, quantity, reason, granted_at) "
                "VALUES ('ak_old', 'api-credit-fulfillment.v1:old', 'weather-api', 'weather-quota', 5, 'issuance', '2026-10-01')"
            ))
        return engine, previous, migrations_module

    def test_the_migration_creates_the_table_and_existing_grants_read_unpinned(self, monkeypatch):
        engine, _, _ = self._previous_head(monkeypatch)
        assert "grant_terms" not in inspect(engine).get_table_names()

        # The chain alone, without create_all, so the step itself creates the table.
        apply_schema_migrations(engine)
        assert {c["name"] for c in inspect(engine).get_columns("grant_terms")} == set(
            Base.metadata.tables["grant_terms"].columns.keys()
        )
        run_migrations(engine)

        assert "grant_terms" in inspect(engine).get_table_names()
        with engine.begin() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM grant_terms")).scalar() == 0
        check_schema_version(engine)

    def test_the_previous_chain_still_validates_the_migrated_schema(self, monkeypatch):
        engine, previous, migrations_module = self._previous_head(monkeypatch)
        run_migrations(engine)

        # The previous image checks the grant table's exact columns and its own
        # chain head, both of which the new step leaves as they were.
        monkeypatch.setattr(migrations_module, "_MIGRATIONS", previous)
        check_schema_version(engine)
        apply_schema_migrations(engine)
