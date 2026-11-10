"""The CLI's listing commands are clients of the running storefront.

The storefront client is replaced at ``_open_storefront``, the one place the
commands reach the storefront through; constructing the storefront's services
or its database fails the test. Every key is a deterministic development value,
never for a public network.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
from arkhai_api_selling.persistence import StorefrontSQLiteClient
from arkhai_api_selling.publish_route import (
    PUBLISH_FROM_QUOTA_OPERATION,
    PUBLISH_FROM_QUOTA_PATH,
)
from market_identity import Ed25519Signer
from storefront_client import StorefrontClientError
from storefront_client.models import ListingListResponse
from typer.testing import CliRunner

from inference_storefront import cli, server
from inference_storefront.utils import config as storefront_config
from tests.cards import model_card

SELLER = Ed25519Signer(b"\x22" * 32)


class _Storefront:
    """The running storefront, as the typed client reaches it."""

    def __init__(self, *, refuse: Exception | None = None) -> None:
        self.opened: list[tuple[str, object]] = []
        self.requests: list[tuple[tuple, dict]] = []
        self.refuse = refuse

    def open(self, url, signer):
        self.opened.append((url, signer))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def authenticated_request(self, *args, **kwargs):
        if self.refuse is not None:
            raise self.refuse
        self.requests.append((args, kwargs))
        return {"status": "created", "listing_id": "L-1"}

    def list_listings(self, *, status=None, limit=50, offset=0):
        if self.refuse is not None:
            raise self.refuse
        self.requests.append(((), {"status": status, "limit": limit, "offset": offset}))
        return ListingListResponse(listings=[], count=0, limit=limit, offset=offset)


def _never_composed(*_args, **_kwargs):
    raise AssertionError("a listing command composed the storefront's services")


def _never_opened(*_args, **_kwargs):
    raise AssertionError("a listing command opened the storefront's database")


def _cli(monkeypatch, storefront: _Storefront) -> CliRunner:
    monkeypatch.setattr(cli, "_open_storefront", storefront.open)
    monkeypatch.setattr(storefront_config, "resolve_identity_signer", lambda: SELLER)
    monkeypatch.setattr(
        storefront_config,
        "resolve_identity_config",
        lambda: SimpleNamespace(principal=SELLER.identity),
    )
    monkeypatch.setattr(server, "_build_inference_services", _never_composed)
    monkeypatch.setattr(StorefrontSQLiteClient, "__init__", _never_opened)
    return CliRunner()


def _publish(card_path) -> list[str]:
    return [
        "publish",
        "--resource-id",
        "svc-quota",
        "--model-card",
        str(card_path),
        "-a",
        "http://seller.test",
    ]


def _card_file(tmp_path):
    path = tmp_path / "card.json"
    path.write_text(json.dumps(model_card()), encoding="utf-8")
    return path


def test_the_publish_command_creates_through_the_running_storefront(monkeypatch, tmp_path):
    storefront = _Storefront()

    result = _cli(monkeypatch, storefront).invoke(cli.app, _publish(_card_file(tmp_path)))

    assert result.exit_code == 0, result.output
    assert storefront.opened == [("http://seller.test", SELLER)]
    ((args, kwargs),) = storefront.requests
    assert args == ("POST", PUBLISH_FROM_QUOTA_PATH)
    assert kwargs["role"] == "seller"
    assert kwargs["operation"] == PUBLISH_FROM_QUOTA_OPERATION
    assert kwargs["body"]["resource_id"] == "svc-quota"
    assert kwargs["body"]["model_card"] == model_card()
    assert '"listing_id": "L-1"' in result.output


def test_the_listings_command_reads_the_running_storefront_without_a_credential(monkeypatch):
    storefront = _Storefront()

    result = _cli(monkeypatch, storefront).invoke(
        cli.app, ["listings", "--status", "open", "-a", "http://seller.test"]
    )

    assert result.exit_code == 0, result.output
    assert storefront.opened == [("http://seller.test", None)]
    assert storefront.requests == [((), {"status": "open", "limit": 50, "offset": 0})]


def test_a_command_no_storefront_answers_fails_naming_where_it_was_sent(monkeypatch, tmp_path):
    storefront = _Storefront(refuse=httpx.ConnectError("connection refused"))

    result = _cli(monkeypatch, storefront).invoke(cli.app, _publish(_card_file(tmp_path)))

    assert result.exit_code == 1
    assert "no storefront answered at http://seller.test (ConnectError)" in result.output


def test_a_refused_create_fails_with_the_storefronts_reason(monkeypatch, tmp_path):
    storefront = _Storefront(
        refuse=StorefrontClientError(
            "settlement mechanism alkahest.v1 cannot be reached yet", status_code=503
        )
    )

    result = _cli(monkeypatch, storefront).invoke(cli.app, _publish(_card_file(tmp_path)))

    assert result.exit_code == 1
    assert "refused: settlement mechanism alkahest.v1 cannot be reached yet" in result.output
