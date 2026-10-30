"""A scripted inference authority behind the storefront's real authority client.

Mocked only at its HTTP boundary, so the recorded request is the one the client
puts on the wire. Every key and address is a deterministic development value.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from arkhai_api.issuance import issuance_request_model, issuance_result_model
from arkhai_api_client import AuthorityClient
from arkhai_inference.label import INFERENCE_LABEL
from market_core import SettlementEvidence
from market_identity import Ed25519Signer

BUYER = Ed25519Signer(bytes.fromhex("11" * 32)).identity
ESCROW_UID = "0x" + "ab" * 32

IssuanceRequest = issuance_request_model(INFERENCE_LABEL)
IssuanceResult = issuance_result_model(INFERENCE_LABEL)


class ScriptedAuthority:
    """Commits every issuance it is sent, recording the request body."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert (request.method, request.url.path) == ("POST", "/api/v1/issuance")
        body = json.loads(request.content)
        self.requests.append(body)
        issued = IssuanceRequest.model_validate(body)
        result = IssuanceResult(
            fulfillment_id=issued.fulfillment_id,
            grant_id=issued.fulfillment_id,
            negotiation_id=issued.negotiation_id,
            owner=issued.owner,
            service=issued.service,
            resource_id=issued.resource_id,
            quantity=issued.quantity,
            key_mode=issued.key.mode,
            key_id=issued.key.key_id or "ik_new",
            balance=issued.quantity,
            request_digest=issued.request_digest,
            committed_at_unix=1_790_000_000,
        )
        return httpx.Response(200, json={**result.model_dump(mode="json"), "secret": "ik_new.s3cret"})

    def client(self) -> AuthorityClient:
        return AuthorityClient(
            "http://inference-authority.test",
            "development-admin-key",
            label=INFERENCE_LABEL,
            transport=httpx.MockTransport(self.handler),
        )


def evidence(accepted_card: dict[str, Any], *, negotiation_id: str = "neg-1", quantity: int = 40) -> SettlementEvidence:
    """Verified Alkahest evidence whose delivery carries ``accepted_card``."""
    return SettlementEvidence(
        negotiation_id,
        "alkahest.v1",
        ESCROW_UID,
        "verified",
        {
            "kind": "inference.settlement-evidence.v1",
            "schema_version": 1,
            "agreement_digest": "a" * 64,
            "source": {"verified_source": "fixture", "obligation_ref": "accepted-obligation"},
            "delivery": {
                "owner": BUYER.model_dump(mode="json"),
                "listing_resource": accepted_card,
                "quantity": quantity,
                "key_mode": "new",
                "key_id": None,
                "listing_id": "L-1",
            },
        },
    )
