"""The startup preflight proves the inference authority accepts this storefront's signed calls.

The authority is scripted at its HTTP boundary behind the storefront's real
authority client, signing its answers as the trusted authority. Every key is a
deterministic development value, never used on a public network.
"""

from __future__ import annotations

import json
import time

import httpx
import pytest
from arkhai_api_client import AuthorityClient
from arkhai_api_contracts import operations
from arkhai_api_contracts.headers import (
    IDENTITY_IDENTIFIER_HEADER,
    IDENTITY_SCHEME_HEADER,
    REQUEST_ID_HEADER,
    ROLE_HEADER,
    SIGNATURE_HEADER,
    SIGNATURE_VERSION_HEADER,
    TIMESTAMP_HEADER,
)
from arkhai_api_contracts.routes import SERVICE_ROLE
from arkhai_inference.label import INFERENCE_LABEL
from market_identity import ResponseEnvelope, TrustedIdentitySet, canonical_body_hash, sign_response

from inference_storefront.startup import (
    PREFLIGHT_PROBE_KEY_ID,
    AuthorityAuthenticationRefused,
    preflight_credits_service,
)
from tests.integration.conftest import AUTHORITY_SIGNER, AUTHORITY_URL, SELLER_SIGNER, replaced

PROBE_PATH = f"/api/v1/keys/{PREFLIGHT_PROBE_KEY_ID}"


class Authority:
    """Answers the key probe with a scripted status, signed unless told otherwise."""

    def __init__(self, probe_status: int, *, signed: bool = True) -> None:
        self.probe_status = probe_status
        self.signed = signed
        self.probes = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert (request.method, request.url.path) == ("GET", PROBE_PATH)
        self.probes += 1
        payload = {"error": "unknown_key" if self.probe_status == 404 else "refused"}
        response = httpx.Response(self.probe_status, json=payload)
        if not self.signed:
            return response
        signed = sign_response(
            signer=AUTHORITY_SIGNER,
            envelope=ResponseEnvelope(
                role=SERVICE_ROLE,
                principal=AUTHORITY_SIGNER.identity,
                method="GET",
                operation=operations.KEY_GET,
                resource=PREFLIGHT_PROBE_KEY_ID,
                request_id=request.headers[REQUEST_ID_HEADER],
                timestamp=int(time.time()),
                status=self.probe_status,
                body_hash=canonical_body_hash(json.loads(response.content)),
            ),
        )
        response.headers.update(
            {
                SIGNATURE_VERSION_HEADER: signed.protocol,
                IDENTITY_SCHEME_HEADER: signed.principal.scheme.value,
                IDENTITY_IDENTIFIER_HEADER: signed.principal.identifier,
                ROLE_HEADER: signed.role,
                REQUEST_ID_HEADER: signed.request_id,
                TIMESTAMP_HEADER: str(signed.timestamp),
                SIGNATURE_HEADER: signed.proof.value,
            }
        )
        return response


async def _preflight(authority: Authority) -> None:
    await _preflight_over(httpx.MockTransport(authority.handler))


async def _preflight_over(transport: httpx.AsyncBaseTransport) -> None:
    client = AuthorityClient(
        AUTHORITY_URL,
        label=INFERENCE_LABEL,
        transport=transport,
        signer=SELLER_SIGNER,
        expected_authorities=TrustedIdentitySet(identities=(AUTHORITY_SIGNER.identity,)),
    )
    try:
        await preflight_credits_service(client)
    finally:
        await client.close()


async def test_a_signed_unknown_key_answer_passes_the_preflight(storefront):
    authority = Authority(404)

    await _preflight(authority)

    assert authority.probes == 1


@pytest.mark.parametrize("status", [401, 403])
async def test_an_authority_refusing_the_signed_call_stops_startup_at_once(storefront, status):
    authority = Authority(status)
    # Not retried, and not excused by fail_on_unreachable.
    with replaced(credits={"service_url": AUTHORITY_URL, "fail_on_unreachable": False}):
        with pytest.raises(AuthorityAuthenticationRefused, match=f"HTTP {status}"):
            await _preflight(authority)

    assert authority.probes == 1


async def test_an_unverifiable_answer_stops_startup_at_once(storefront):
    authority = Authority(404, signed=False)

    with pytest.raises(AuthorityAuthenticationRefused, match="verifiable signature"):
        await _preflight(authority)

    assert authority.probes == 1


async def test_an_authority_answering_but_never_accepting_the_probe_stops_startup(storefront):
    authority = Authority(503)
    # A signed answer is not an outage, so fail_on_unreachable does not excuse it.
    with replaced(
        credits={"service_url": AUTHORITY_URL, "fail_on_unreachable": False, "preflight_timeout": 1}
    ):
        with pytest.raises(RuntimeError, match="did not accept the signed probe"):
            await _preflight(authority)

    assert authority.probes >= 1


async def test_only_a_transport_outage_is_excused_by_fail_on_unreachable(storefront):
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with replaced(
        credits={"service_url": AUTHORITY_URL, "fail_on_unreachable": False, "preflight_timeout": 1}
    ):
        await _preflight_over(httpx.MockTransport(unreachable))
    with replaced(credits={"service_url": AUTHORITY_URL, "preflight_timeout": 1}):
        with pytest.raises(RuntimeError, match="unreachable"):
            await _preflight_over(httpx.MockTransport(unreachable))
