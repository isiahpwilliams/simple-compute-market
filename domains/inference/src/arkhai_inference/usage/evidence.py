"""Canonical, signed, secret-free inference usage evidence."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Self

from market_core.schemas import Uint256Amount
from market_identity import (
    Identity,
    SignatureProof,
    Signer,
    TrustedIdentitySet,
    canonical_json,
    get_identity_verifier,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from arkhai_inference.listings.models import AttestationEnvelope, InferenceRateCard
from arkhai_inference.usage.models import InferenceUsageRecord, derive_charge

EVIDENCE_PROTOCOL = "arkhai.inference.usage-evidence.v1"
EVIDENCE_CAPABILITY = "inference.usage.v1"
_SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,511}$")
_MAX_EVIDENCE_BYTES = 32_768


class UsageEvidenceError(ValueError):
    """Signed evidence is malformed, untrusted, stale, or mis-charged."""


class _EvidenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InferenceUsageEvidenceBodyV1(_EvidenceContract):
    """Public usage fact signed by the authority or storefront that metered it."""

    protocol: Literal["arkhai.inference.usage-evidence.v1"] = EVIDENCE_PROTOCOL
    schema_version: Literal["1"] = "1"
    capability: Literal["inference.usage.v1"] = EVIDENCE_CAPABILITY
    domain: Literal["inference"] = "inference"
    record: InferenceUsageRecord
    rate_card: InferenceRateCard
    charge: Uint256Amount
    grant_id: str = Field(min_length=1, max_length=512)
    fulfillment_id: str = Field(min_length=1, max_length=512)
    issuer: Identity
    recorded_at_unix: int = Field(ge=0)
    attestation: AttestationEnvelope | None = None

    @model_validator(mode="after")
    def validate_bindings(self) -> Self:
        for field_name in ("grant_id", "fulfillment_id"):
            if not _SAFE_REF.fullmatch(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be a safe opaque reference")
        if self.charge != derive_charge(self.record, self.rate_card):
            raise ValueError("charge does not match the record under the pinned rate card")
        return self


class SignedInferenceUsageEvidenceV1(_EvidenceContract):
    """Evidence body plus one scheme-matched marketplace signature."""

    body: InferenceUsageEvidenceBodyV1
    proof: SignatureProof

    @model_validator(mode="after")
    def proof_matches_issuer(self) -> Self:
        if self.proof.scheme != self.body.issuer.scheme:
            raise ValueError("evidence proof scheme does not match issuer")
        return self


class ExpectedInferenceUsageEvidenceV1(_EvidenceContract):
    """Grant and request facts evidence must match.

    A body is self-consistent even for another grant or another request, so
    the consumer states which one it is settling. The grant and request
    identities together name one usage record; charging that pair once is
    the consumer's rule, and binding here is what lets it hold it.
    """

    grant_id: str
    fulfillment_id: str
    request_id: str
    key_id: str
    model_id: str
    rate_card: InferenceRateCard
    issuer: Identity


def _evidence_signing_bytes(body: InferenceUsageEvidenceBodyV1) -> bytes:
    return EVIDENCE_PROTOCOL.encode() + b"\0" + canonical_json(
        body.model_dump(mode="json")
    )


def sign_inference_usage_evidence(
    body: InferenceUsageEvidenceBodyV1,
    signer: Signer,
) -> SignedInferenceUsageEvidenceV1:
    """Sign one canonical evidence body with its declared issuer."""

    if signer.identity != body.issuer:
        raise UsageEvidenceError("evidence signer does not match issuer")
    proof = SignatureProof.from_bytes(
        signer.identity.scheme,
        signer.sign(_evidence_signing_bytes(body)),
    )
    return SignedInferenceUsageEvidenceV1(body=body, proof=proof)


def canonical_signed_usage_evidence(
    evidence: SignedInferenceUsageEvidenceV1,
) -> str:
    """Encode the signed object in the only admitted JSON representation."""

    return canonical_json(evidence.model_dump(mode="json")).decode("utf-8")


def usage_evidence_digest(evidence: SignedInferenceUsageEvidenceV1) -> str:
    encoded = canonical_signed_usage_evidence(evidence).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def decode_signed_usage_evidence(value: str | bytes) -> SignedInferenceUsageEvidenceV1:
    """Decode bounded canonical evidence and reject alternate JSON encodings."""

    raw = value.encode("utf-8") if isinstance(value, str) else value
    if len(raw) > _MAX_EVIDENCE_BYTES:
        raise UsageEvidenceError("usage evidence exceeds size limit")
    try:
        decoded = json.loads(raw)
        evidence = SignedInferenceUsageEvidenceV1.model_validate(decoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise UsageEvidenceError("invalid signed usage evidence") from exc
    if canonical_signed_usage_evidence(evidence).encode("utf-8") != raw:
        raise UsageEvidenceError("usage evidence must use canonical JSON")
    return evidence


def verify_inference_usage_evidence(
    evidence: SignedInferenceUsageEvidenceV1,
    *,
    trusted_issuers: TrustedIdentitySet,
    expected: ExpectedInferenceUsageEvidenceV1,
    now_unix: int,
    max_future_skew_seconds: int = 30,
    max_age_seconds: int | None = None,
) -> InferenceUsageEvidenceBodyV1:
    """Age is bounded only when ``max_age_seconds`` is given; attestation is ignored."""

    body = evidence.body
    if body.issuer not in trusted_issuers or body.issuer != expected.issuer:
        raise UsageEvidenceError("usage evidence issuer is not trusted")
    verifier = get_identity_verifier(body.issuer.scheme)
    if not verifier.verify_signature(
        body.issuer,
        _evidence_signing_bytes(body),
        evidence.proof.to_bytes(),
    ):
        raise UsageEvidenceError("usage evidence signature is invalid")
    if body.recorded_at_unix > now_unix + max_future_skew_seconds:
        raise UsageEvidenceError("usage evidence is recorded in the future")
    if max_age_seconds is not None and body.recorded_at_unix < now_unix - max_age_seconds:
        raise UsageEvidenceError("usage evidence is stale")

    facts = (
        ("grant_id", body.grant_id, expected.grant_id),
        ("fulfillment_id", body.fulfillment_id, expected.fulfillment_id),
        ("request_id", body.record.request_id, expected.request_id),
        ("key_id", body.record.key_id, expected.key_id),
        ("model_id", body.record.model_id, expected.model_id),
        ("rate_card", body.rate_card, expected.rate_card),
    )
    for name, actual, wanted in facts:
        if actual != wanted:
            raise UsageEvidenceError(f"usage evidence {name} does not match the grant")
    return body
