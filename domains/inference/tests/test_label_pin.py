"""One fixed issuance request pins the digest bytes the authority must reproduce."""

from __future__ import annotations

from market_identity import Ed25519Signer

from arkhai_inference.settlement import credits_client, issuance_evidence

PINNED_NEGOTIATION_ID = "negotiation-pin-1"
PINNED_OWNER_SEED = bytes(range(32))
PINNED_FULFILLMENT_ID = (
    "inference-fulfillment.v1:"
    "2238e6684afc8927275e91783f58b0ecb672250ee9b32c85003ac8d68f4f7a35"
)
PINNED_REQUEST_DIGEST = (
    "sha256:a19cc6fa68052fecc44174aaf5503fce2e4ed8639be6d7e8c762e67e81d78d91"
)

_API_CREDITS_LABELS = {
    "issuance_request": "arkhai.api-credits.issuance-request.v1",
    "issuance_result": "arkhai.api-credits.issuance-result.v1",
    "evidence_protocol": "arkhai.api-credits.issuance-evidence.v1",
    "evidence_capability": "api-credits.issuance.v1",
    "portable_ref": "arkhai.api-credits.portable-fulfillment-ref.v1",
    "fulfillment_prefix": "api-credit-fulfillment.v1:",
}

INFERENCE_LABELS = {
    "issuance_request": credits_client.ISSUANCE_REQUEST_SCHEMA,
    "issuance_result": credits_client.ISSUANCE_RESULT_SCHEMA,
    "evidence_protocol": issuance_evidence.EVIDENCE_PROTOCOL,
    "evidence_capability": issuance_evidence.EVIDENCE_CAPABILITY,
    "portable_ref": issuance_evidence.PORTABLE_FULFILLMENT_REF_SCHEMA,
    "fulfillment_prefix": "inference-fulfillment.v1:",
}


def pinned_request() -> credits_client.CreditIssuanceRequest:
    owner = Ed25519Signer(PINNED_OWNER_SEED).identity
    return credits_client.CreditIssuanceRequest.create(
        negotiation_id=PINNED_NEGOTIATION_ID,
        owner=owner,
        service="llama-3.1-8b",
        resource_id="quota-1",
        quantity=10,
        key=credits_client.CreditKeyTarget(mode="new"),
    )


def test_the_fixed_request_digests_to_the_pinned_bytes():
    request = pinned_request()
    assert request.fulfillment_id == PINNED_FULFILLMENT_ID
    assert request.request_digest == PINNED_REQUEST_DIGEST
    assert credits_client.derive_credit_fulfillment_id(PINNED_NEGOTIATION_ID) == PINNED_FULFILLMENT_ID


def test_every_label_carries_the_inference_name():
    assert INFERENCE_LABELS == {
        "issuance_request": "arkhai.inference.issuance-request.v1",
        "issuance_result": "arkhai.inference.issuance-result.v1",
        "evidence_protocol": "arkhai.inference.issuance-evidence.v1",
        "evidence_capability": "inference.issuance.v1",
        "portable_ref": "arkhai.inference.portable-fulfillment-ref.v1",
        "fulfillment_prefix": "inference-fulfillment.v1:",
    }


def test_no_label_equals_the_api_credits_value():
    for name, value in INFERENCE_LABELS.items():
        assert value != _API_CREDITS_LABELS[name], name
    assert not PINNED_FULFILLMENT_ID.startswith(_API_CREDITS_LABELS["fulfillment_prefix"])
