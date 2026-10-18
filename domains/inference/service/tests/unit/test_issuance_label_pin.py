"""The authority's digest of the pinned request equals the client's bytes."""

from __future__ import annotations

from market_identity import Ed25519Signer

from inference_service.models.keys_model import (
    ISSUANCE_REQUEST_SCHEMA,
    ISSUANCE_RESULT_SCHEMA,
    KeyDisposition,
    derive_credit_fulfillment_id,
    issuance_request_digest,
)

PINNED_NEGOTIATION_ID = "negotiation-pin-1"
PINNED_OWNER_SEED = bytes(range(32))
PINNED_FULFILLMENT_ID = (
    "inference-fulfillment.v1:"
    "2238e6684afc8927275e91783f58b0ecb672250ee9b32c85003ac8d68f4f7a35"
)
PINNED_REQUEST_DIGEST = (
    "sha256:a19cc6fa68052fecc44174aaf5503fce2e4ed8639be6d7e8c762e67e81d78d91"
)


def test_the_authority_derives_the_pinned_bytes():
    owner = Ed25519Signer(PINNED_OWNER_SEED).identity
    fulfillment_id = derive_credit_fulfillment_id(PINNED_NEGOTIATION_ID)
    assert fulfillment_id == PINNED_FULFILLMENT_ID
    assert issuance_request_digest(
        fulfillment_id=fulfillment_id,
        negotiation_id=PINNED_NEGOTIATION_ID,
        owner=owner,
        service="llama-3.1-8b",
        resource_id="quota-1",
        quantity=10,
        key=KeyDisposition(mode="new"),
    ) == PINNED_REQUEST_DIGEST


def test_the_authority_names_the_inference_schemas():
    assert ISSUANCE_REQUEST_SCHEMA == "arkhai.inference.issuance-request.v1"
    assert ISSUANCE_RESULT_SCHEMA == "arkhai.inference.issuance-result.v1"
