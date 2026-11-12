"""The service's migration chain and its command, ``apicredits-service-migrate [--check]``.

The chain is the family authority's, named for this service. The command loads
the layered settings without the application's secrets, so it runs before they
are mounted; Compose runs it before the application, and ``make migrate`` runs
it for local development outside Docker.
"""

from __future__ import annotations

from collections.abc import Sequence

from arkhai_api_authority import authority_chain
from arkhai_api_authority.migrate import main as run_migration_command

from apicredits_service.settings_source import load_settings_source

CHAIN = authority_chain(
    service="the API-credit service", command="apicredits-service-migrate"
)


def main(argv: Sequence[str] | None = None) -> None:
    run_migration_command(CHAIN, load_settings_source, argv)


if __name__ == "__main__":
    main()
