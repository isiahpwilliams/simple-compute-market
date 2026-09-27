"""Canonical, signed, secret-free inference usage evidence."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Self

from market_identity import (
    Identity,
    SignatureProof,
    Signer,
    TrustedIdentitySet,
    canonical_json,
    get_identity_verifier,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from domains.inference.listings.models import AttestationEnvelope, InferenceRateCard
from domains.inference.usage.models import InferenceUsageRecord, derive_charge

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
    charge: int = Field(ge=0)
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
    now_unix: int,
    max_future_skew_seconds: int = 30,
) -> InferenceUsageEvidenceBodyV1:
    """Verify signature, trust, timeliness, and the charge; ignore attestation."""

    body = evidence.body
    if body.issuer not in trusted_issuers:
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
    return body
