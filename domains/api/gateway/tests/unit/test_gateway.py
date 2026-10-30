"""The gateway's request ordering against a fake gate and a fake model server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from arkhai_api_gate import GateDecision, PurchasePointer, TokenGate, VerifiedKey
from arkhai_api_gateway import (
    INVALID_REQUEST,
    MODEL_NOT_FOUND,
    UPSTREAM_UNAVAILABLE,
    GatewayOffering,
    VerificationRefusal,
    create_gateway_app,
)

SERVICE = "served-model"
BUYER_SECRET = "k_1.buyer-secret"
UPSTREAM_SECRET = "upstream-secret"
INFERENCE_TERMS = {"rate_card": {"request_credits": "1"}, "attestation": {"kind": None}}
PINNED_DIGEST = "sha256:" + "a" * 64


class Upstream:
    """A model server that records what reached it and answers a fixed completion."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            201, json={"object": "chat.completion", "path": request.url.path},
        )


def _offering(tmp_path: Path, **overrides: Any) -> GatewayOffering:
    credential = tmp_path / "upstream-credential"
    credential.write_text(UPSTREAM_SECRET + "\n", encoding="utf-8")
    values: dict[str, Any] = {
        "service": SERVICE,
        "scope_service": SERVICE,
        "scope_resource_id": "quota-1",
        "default_charge": 5,
        "purchase": PurchasePointer(service_name=SERVICE),
        "upstream_base_url": "http://model/v1/",
        "upstream_credential_file": credential,
        "current_terms": INFERENCE_TERMS,
    }
    values.update(overrides)
    return GatewayOffering(**values)


def _gate(verified: GateDecision | VerifiedKey, charged: GateDecision | None = None) -> MagicMock:
    gate = MagicMock(spec=TokenGate)
    gate.verify = AsyncMock(return_value=verified)
    gate.charge = AsyncMock(return_value=charged or GateDecision(allowed=True, key_id="k_1"))
    return gate


async def _post(
    offering: GatewayOffering,
    gate: MagicMock,
    upstream: Upstream,
    body: Any,
    *,
    path: str = "/v1/chat/completions",
    verification: Any = None,
) -> httpx.Response:
    http = httpx.AsyncClient(transport=httpx.MockTransport(upstream.handle))
    kwargs = {"verification": verification} if verification is not None else {}
    app = create_gateway_app(offering, gate, http=http, **kwargs)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway",
    ) as client:
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return await client.post(
            path,
            content=content,
            headers={"authorization": f"Bearer {BUYER_SECRET}", "content-type": "application/json"},
        )


def _verified(**terms: Any) -> VerifiedKey:
    return VerifiedKey(key_id="k_1", **terms)


async def test_an_unlisted_model_is_refused_before_the_gate(tmp_path: Path) -> None:
    gate, upstream = _gate(_verified()), Upstream()

    response = await _post(_offering(tmp_path), gate, upstream, {"model": "other"})

    assert response.status_code == 404
    assert response.json() == {"error": MODEL_NOT_FOUND}
    gate.verify.assert_not_awaited()
    gate.charge.assert_not_awaited()
    assert upstream.requests == []


@pytest.mark.parametrize("body", [b"not json", b"[]", {"messages": []}, {"model": 3}])
async def test_a_body_naming_no_model_is_refused_before_the_gate(tmp_path: Path, body: Any) -> None:
    gate, upstream = _gate(_verified()), Upstream()

    response = await _post(_offering(tmp_path), gate, upstream, body)

    assert response.status_code == 400
    assert response.json() == {"error": INVALID_REQUEST}
    gate.verify.assert_not_awaited()
    assert upstream.requests == []


@pytest.mark.parametrize(
    "denial",
    [
        GateDecision(allowed=False, status=401, body={"error": "invalid_api_key"}),
        GateDecision(allowed=False, status=403, body={"error": "key_revoked"}),
        GateDecision(allowed=False, status=403, body={"error": "key_out_of_scope"}),
    ],
)
async def test_a_verify_denial_is_returned_uncharged(tmp_path: Path, denial: GateDecision) -> None:
    gate, upstream = _gate(denial), Upstream()

    response = await _post(_offering(tmp_path), gate, upstream, {"model": SERVICE})

    assert response.status_code == denial.status
    assert response.json() == denial.body
    gate.verify.assert_awaited_once_with(f"Bearer {BUYER_SECRET}")
    gate.charge.assert_not_awaited()
    assert upstream.requests == []


async def test_the_hook_receives_current_and_accepted_terms_and_refuses_uncharged(
    tmp_path: Path,
) -> None:
    accepted = {"rate_card": {"request_credits": "2"}, "attestation": {"kind": None}}
    gate, upstream = _gate(_verified(accepted_terms=accepted, terms_digest=PINNED_DIGEST)), Upstream()
    hook = AsyncMock(return_value=VerificationRefusal(status=409, error="terms_changed"))

    response = await _post(_offering(tmp_path), gate, upstream, {"model": SERVICE}, verification=hook)

    assert response.status_code == 409
    assert response.json() == {"error": "terms_changed"}
    hook.assert_awaited_once_with(INFERENCE_TERMS, accepted, PINNED_DIGEST)
    gate.charge.assert_not_awaited()
    assert upstream.requests == []


async def test_an_admitted_request_charges_the_verified_key_and_forwards(tmp_path: Path) -> None:
    verified = _verified(request_charge=2, terms_digest=PINNED_DIGEST, accepted_terms={})
    gate, upstream = _gate(verified), Upstream()

    response = await _post(_offering(tmp_path), gate, upstream, {"model": SERVICE})

    assert response.status_code == 201
    assert response.json() == {"object": "chat.completion", "path": "/v1/chat/completions"}
    gate.charge.assert_awaited_once_with(verified)
    assert len(upstream.requests) == 1


async def test_completions_forward_under_the_upstream_base_url(tmp_path: Path) -> None:
    gate, upstream = _gate(_verified()), Upstream()

    response = await _post(
        _offering(tmp_path), gate, upstream, {"model": SERVICE}, path="/v1/completions",
    )

    assert response.status_code == 201
    assert str(upstream.requests[0].url) == "http://model/v1/completions"


async def test_an_exhausted_key_is_answered_with_the_charge_denial(tmp_path: Path) -> None:
    exhausted = GateDecision(
        allowed=False, status=402,
        body={"error": "insufficient_credits", "purchase": {"service_name": SERVICE}},
    )
    gate, upstream = _gate(_verified(), exhausted), Upstream()

    response = await _post(_offering(tmp_path), gate, upstream, {"model": SERVICE})

    assert response.status_code == 402
    assert response.json() == exhausted.body
    assert upstream.requests == []


async def test_the_upstream_receives_the_deployments_credential_never_the_buyers(
    tmp_path: Path,
) -> None:
    gate, upstream = _gate(_verified()), Upstream()
    body = {"model": SERVICE, "messages": [{"role": "user", "content": "hi"}]}

    await _post(_offering(tmp_path), gate, upstream, body)

    (sent,) = upstream.requests
    assert sent.headers["authorization"] == f"Bearer {UPSTREAM_SECRET}"
    assert BUYER_SECRET not in str(sent.headers)
    assert json.loads(sent.content) == body


async def test_an_upstream_without_a_credential_receives_no_authorization(tmp_path: Path) -> None:
    gate, upstream = _gate(_verified()), Upstream()

    await _post(_offering(tmp_path, upstream_credential_file=None), gate, upstream, {"model": SERVICE})

    assert "authorization" not in upstream.requests[0].headers


async def test_an_unreachable_upstream_is_a_bad_gateway(tmp_path: Path) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    gate = _gate(_verified())
    app = create_gateway_app(
        _offering(tmp_path), gate, http=httpx.AsyncClient(transport=httpx.MockTransport(refuse)),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway",
    ) as client:
        response = await client.post("/v1/chat/completions", json={"model": SERVICE})

    assert response.status_code == 502
    assert response.json() == {"error": UPSTREAM_UNAVAILABLE}


async def test_models_lists_only_the_offerings_service_ungated(tmp_path: Path) -> None:
    gate = _gate(_verified())
    app = create_gateway_app(_offering(tmp_path), gate, http=httpx.AsyncClient())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway",
    ) as client:
        models = await client.get("/v1/models")
        health = await client.get("/health")

    assert models.json() == {"object": "list", "data": [{"id": SERVICE, "object": "model"}]}
    assert health.json() == {"status": "ok"}
    gate.verify.assert_not_awaited()


def test_a_missing_upstream_credential_fails_at_construction(tmp_path: Path) -> None:
    offering = _offering(tmp_path, upstream_credential_file=tmp_path / "absent")

    with pytest.raises(ValueError, match="regular file"):
        create_gateway_app(offering, _gate(_verified()), http=httpx.AsyncClient())


async def test_two_domains_offerings_behave_alike_save_their_values(tmp_path: Path) -> None:
    """One offering projected as an API-credits root would, one as inference's."""
    credits = _offering(
        tmp_path,
        service="forecast",
        scope_service="forecast",
        scope_resource_id=None,
        default_charge=3,
        current_terms=None,
    )
    inference = _offering(tmp_path)
    for offering in (credits, inference):
        gate, upstream = _gate(_verified()), Upstream()

        unlisted = await _post(offering, gate, upstream, {"model": "unlisted"})
        admitted = await _post(offering, gate, upstream, {"model": offering.service})

        assert unlisted.status_code == 404
        assert admitted.status_code == 201
        gate.charge.assert_awaited_once()
        assert len(upstream.requests) == 1
