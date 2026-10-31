"""Inference storefront admin CLI — the `inference-storefront` console script."""

from __future__ import annotations

import asyncio
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import typer
from market_config.config_loader import set_user_config_path

app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        try:
            __version__ = version("arkhai-inference-storefront")
        except PackageNotFoundError:
            __version__ = "unknown (not installed)"
        typer.echo(f"inference-storefront version {__version__}")
        raise typer.Exit()


def _config_path_callback(value: str | None) -> str | None:
    if value:
        set_user_config_path(Path(value))
    return value


@app.callback()
def main(
    version_flag: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    config_file: str | None = typer.Option(
        None,
        "--config",
        callback=_config_path_callback,
        is_eager=True,
        help="Path to an explicit storefront.toml.",
    ),
) -> None:
    """inference-storefront — seller-side admin CLI for the inference domain."""


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind interface."),
    port: int | None = typer.Option(None, "--port", help="Override port from config."),
) -> None:
    """Run the storefront HTTP server (uvicorn, foreground)."""
    # Imported only once ``--config`` has run: the storefront's settings
    # resolve when its config module is first imported.
    from inference_storefront.server import run_serve

    run_serve(host=host, port=port)


@app.command("publish")
def publish_cmd(
    resource_id: str = typer.Option(
        ...,
        "--resource-id",
        help="Quota resource in the inference authority's ledger the listing derives from.",
    ),
    model_card: Path = typer.Option(
        ...,
        "--model-card",
        exists=True,
        dir_okay=False,
        help="JSON file holding the model card the listing publishes.",
    ),
    price_per_token: str | None = typer.Option(
        None,
        "--price-per-token",
        help=(
            "Optional Alkahest rate in base units per token; omit to publish "
            "configured settlement clauses only."
        ),
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        help="Alkahest payment token contract address (0x…).",
    ),
    chain: str | None = typer.Option(
        None,
        "--chain",
        help="Alkahest chain name from [chains.<name>] config.",
    ),
    escrow_address: str | None = typer.Option(
        None,
        "--escrow-address",
        help="Alkahest escrow contract; resolved from the chain config when omitted.",
    ),
    paused: bool = typer.Option(False, "--paused"),
) -> None:
    """Create + publish a model-card listing backed by a quota resource.

    Pass the Alkahest rate, token, and chain together to publish an escrow
    option. Omit all three to publish the configured settlement clauses.
    The card's resource, site, and offering mode are taken from the quota.
    """
    # Imported only once ``--config`` has run: the storefront's settings
    # resolve when its config module is first imported.
    import inference_storefront.container as _container
    from inference_storefront.domain_runtime import get_market_domain_contract
    from inference_storefront.server import _build_inference_services
    from inference_storefront.utils.config import CHAINS

    escrow_requested = any(
        value is not None for value in (price_per_token, token, chain)
    )
    if escrow_address is not None and not escrow_requested:
        typer.echo(
            "--escrow-address requires the Alkahest rate, token, and chain.", err=True
        )
        raise typer.Exit(code=2)
    accepted_escrows: list[dict[str, Any]] = []
    if escrow_requested:
        if price_per_token is None or token is None or chain is None:
            typer.echo(
                "Alkahest publication requires --price-per-token, --token, and --chain together.",
                err=True,
            )
            raise typer.Exit(code=2)
        if not price_per_token.strip().isdigit():
            typer.echo("--price-per-token must be a base-unit integer", err=True)
            raise typer.Exit(code=2)

        address_config_path = None
        if not escrow_address:
            chain_cfg = CHAINS.get(chain)
            if chain_cfg is None:
                typer.echo(f"chain {chain!r} is not configured", err=True)
                raise typer.Exit(code=2)
            address_config_path = chain_cfg.alkahest_address_config_path
        accepted_escrows = [
            _container.ALKAHEST_STAGE.accepted_escrow(
                chain_name=chain,
                address_config_path=address_config_path,
                token=token,
                price_per_token=price_per_token,
                escrow_address=escrow_address,
            )
        ]

    # The same services the running storefront composes, including the signer
    # its capacity runtime reads.
    services = _build_inference_services(get_market_domain_contract())
    _container.resolved_marketplace_signer = services.marketplace_signer
    _container.resolved_sqlite_client = services.sqlite_client
    result = asyncio.run(
        services.listing_service.publish_from_quota(
            resource_id=resource_id,
            accepted_escrows=accepted_escrows,
            model_card=json.loads(model_card.read_text(encoding="utf-8")),
            paused=paused,
        )
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("listings")
def listings_cmd(
    status: str | None = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    """List the storefront's local listings."""
    # Imported only once ``--config`` has run, as in ``publish``.
    from inference_storefront.utils.config import (
        BASE_URL_OVERRIDE,
        resolve_identity_config,
    )
    from inference_storefront.container import get_sqlite_client

    rows = asyncio.run(
        get_sqlite_client(
            local_listing_principal=resolve_identity_config().principal,
            expected_legacy_sellers=(BASE_URL_OVERRIDE,),
        ).list_listings(status=status, limit=limit),
    )
    typer.echo(json.dumps(rows, indent=2, default=str))


if __name__ == "__main__":
    app()
