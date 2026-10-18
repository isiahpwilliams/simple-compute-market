"""Both listing entry points reach the composed listing service with what was asked."""

from __future__ import annotations

import json
from types import SimpleNamespace

from typer.testing import CliRunner

import inference_storefront.container as container
from inference_storefront import cli, server
from inference_storefront.controllers.listings_controller import (
    ListingsController,
    PublishFromQuotaRequest,
)


class _ListingService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def publish_from_quota(self, **request):
        self.calls.append(request)
        return {"status": "created", "listing_id": "L-1"}


async def test_the_publish_route_passes_the_submitted_settlement_clauses():
    service = _ListingService()
    controller = ListingsController.__new__(ListingsController)
    controller._listing_svc = service
    clauses = [{"mechanism": "alkahest.v1", "chain": "anvil"}]

    await controller.publish_from_quota(
        PublishFromQuotaRequest(
            resource_id="svc-quota", model_card={"served_model_name": "atlas-7b"}, settlement_clauses=clauses
        )
    )

    assert service.calls[0]["settlement_clauses"] == clauses


def test_the_publish_command_uses_the_storefronts_composed_listing_service(monkeypatch, tmp_path):
    service = _ListingService()
    card = tmp_path / "card.json"
    card.write_text(json.dumps({"served_model_name": "atlas-7b"}))
    signer = SimpleNamespace(identity="seller")
    # The command sets these on the container; monkeypatch restores them.
    monkeypatch.setattr(container, "resolved_marketplace_signer", None)
    monkeypatch.setattr(container, "resolved_sqlite_client", None)
    monkeypatch.setattr(
        server,
        "_build_inference_services",
        lambda domain: SimpleNamespace(
            listing_service=service, marketplace_signer=signer, sqlite_client=object()
        ),
    )

    result = CliRunner().invoke(
        cli.app,
        ["publish", "--resource-id", "svc-quota", "--model-card", str(card)],
    )

    assert result.exit_code == 0, result.output
    assert service.calls[0]["resource_id"] == "svc-quota"
    assert service.calls[0]["model_card"] == {"served_model_name": "atlas-7b"}
