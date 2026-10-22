"""Signed usage evidence is canonical, verifiable, and secret-free."""

from __future__ import annotations

import json

import pytest
from market_identity import Ed25519Signer, TrustedIdentitySet
from pydantic import ValidationError

from arkhai_inference.usage.evidence import (
    ExpectedInferenceUsageEvidenceV1,
    InferenceUsageEvidenceBodyV1,
    UsageEvidenceError,
    canonical_signed_usage_evidence,
    decode_signed_usage_evidence,
    sign_inference_usage_evidence,
    usage_evidence_digest,
    verify_inference_usage_evidence,
)

_SECRET = "ak_1.SECRET-BEARER-MATERIAL"
_PROMPT = "PROMPT-TEXT-MUST-NOT-LEAK"
_COMPLETION = "COMPLETION-TEXT-MUST-NOT-LEAK"
_NOW = 2_000_000_000
_ASSET = "0x" + "01" * 20
_RATE_CARD = {"asset": _ASSET, "prompt_credits_per_million": 500, "completion_credits_per_million": 1500}


def _issue(*, bearer_secret, prompt, completion, prompt_tokens=1_000_000, completion_tokens=2_000_000, outcome="completed", **extra):
    # The producing side holds the secret and the texts; the body may carry none.
    del bearer_secret, prompt, completion
    return {
        "record": {
            "model_id": "meta-llama/llama-3.1-8b-instruct",
            "key_id": "ak_1",
            "request_id": "req-1",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "outcome": outcome,
        },
        "rate_card": _RATE_CARD,
        "charge": 3500 if outcome != "failed" else 0,
        "grant_id": "inference-fulfillment.v1:" + "a" * 64,
        "fulfillment_id": "inference-fulfillment.v1:" + "a" * 64,
        "recorded_at_unix": _NOW,
        **extra,
    }


def _fixture(**extra):
    signer = Ed25519Signer(bytes(range(32)))
    body = InferenceUsageEvidenceBodyV1.model_validate(
        _issue(bearer_secret=_SECRET, prompt=_PROMPT, completion=_COMPLETION, issuer=signer.identity, **extra)
    )
    return signer, body


def _expected(body, **overrides):
    facts = {
        "grant_id": body.grant_id,
        "fulfillment_id": body.fulfillment_id,
        "request_id": body.record.request_id,
        "key_id": body.record.key_id,
        "model_id": body.record.model_id,
        "rate_card": body.rate_card,
        "issuer": body.issuer,
    }
    facts.update(overrides)
    return ExpectedInferenceUsageEvidenceV1.model_validate(facts)


def _verify(evidence, signer, body, **kwargs):
    kwargs.setdefault("trusted_issuers", TrustedIdentitySet(identities=(signer.identity,)))
    kwargs.setdefault("expected", _expected(body))
    kwargs.setdefault("now_unix", _NOW)
    return verify_inference_usage_evidence(evidence, **kwargs)


def test_signed_evidence_is_canonical_verifiable_and_secret_free():
    signer, body = _fixture()
    evidence = sign_inference_usage_evidence(body, signer)
    encoded = canonical_signed_usage_evidence(evidence)
    for canary in (_SECRET, _PROMPT, _COMPLETION):
        assert canary not in encoded
    assert decode_signed_usage_evidence(encoded) == evidence
    assert usage_evidence_digest(evidence).startswith("sha256:")
    assert _verify(evidence, signer, body) == body


def test_body_rejects_a_charge_that_does_not_match_the_card():
    signer = Ed25519Signer(bytes(range(32)))
    with pytest.raises(ValidationError, match="charge does not match"):
        InferenceUsageEvidenceBodyV1.model_validate(
            _issue(bearer_secret=_SECRET, prompt=_PROMPT, completion=_COMPLETION, issuer=signer.identity, charge=1)
        )


def test_tampered_charge_fails_to_decode():
    signer, body = _fixture()
    encoded = canonical_signed_usage_evidence(sign_inference_usage_evidence(body, signer))
    tampered = json.loads(encoded)
    tampered["body"]["charge"] = 1
    with pytest.raises(UsageEvidenceError):
        decode_signed_usage_evidence(json.dumps(tampered, separators=(",", ":"), sort_keys=True))


def test_non_canonical_encoding_is_rejected():
    signer, body = _fixture()
    encoded = canonical_signed_usage_evidence(sign_inference_usage_evidence(body, signer))
    with pytest.raises(UsageEvidenceError, match="canonical"):
        decode_signed_usage_evidence(json.dumps(json.loads(encoded), indent=2))


def test_untrusted_issuer_is_rejected():
    signer, body = _fixture()
    evidence = sign_inference_usage_evidence(body, signer)
    other = Ed25519Signer(bytes(range(1, 33)))
    with pytest.raises(UsageEvidenceError, match="not trusted"):
        _verify(evidence, signer, body, trusted_issuers=TrustedIdentitySet(identities=(other.identity,)))
    with pytest.raises(UsageEvidenceError, match="not trusted"):
        _verify(evidence, signer, body, expected=_expected(body, issuer=other.identity))


def test_signer_must_be_the_declared_issuer():
    _, body = _fixture()
    with pytest.raises(UsageEvidenceError, match="does not match issuer"):
        sign_inference_usage_evidence(body, Ed25519Signer(bytes(range(1, 33))))


def test_forged_signature_is_rejected():
    signer, body = _fixture()
    evidence = sign_inference_usage_evidence(body, signer)
    forged = evidence.model_copy(update={"body": body.model_copy(update={"recorded_at_unix": _NOW - 1})})
    with pytest.raises(UsageEvidenceError, match="signature is invalid"):
        _verify(forged, signer, body)


def test_future_dated_evidence_is_rejected():
    signer, body = _fixture()
    evidence = sign_inference_usage_evidence(body, signer)
    with pytest.raises(UsageEvidenceError, match="future"):
        _verify(evidence, signer, body, now_unix=_NOW - 3600)


def test_evidence_older_than_the_retention_bound_is_stale():
    signer, body = _fixture()
    evidence = sign_inference_usage_evidence(body, signer)
    assert _verify(evidence, signer, body, now_unix=_NOW + 3600, max_age_seconds=3600) == body
    with pytest.raises(UsageEvidenceError, match="stale"):
        _verify(evidence, signer, body, now_unix=_NOW + 3601, max_age_seconds=3600)


@pytest.mark.parametrize(
    "fact,value",
    [
        ("grant_id", "inference-fulfillment.v1:" + "b" * 64),
        ("fulfillment_id", "inference-fulfillment.v1:" + "b" * 64),
        ("request_id", "req-2"),
        ("key_id", "ak_2"),
        ("model_id", "meta-llama/llama-3.1-70b-instruct"),
        ("rate_card", {**_RATE_CARD, "completion_credits_per_million": 1600}),
    ],
)
def test_evidence_for_another_grant_is_refused(fact, value):
    signer, body = _fixture()
    evidence = sign_inference_usage_evidence(body, signer)
    with pytest.raises(UsageEvidenceError, match=f"{fact} does not match"):
        _verify(evidence, signer, body, expected=_expected(body, **{fact: value}))


def test_attestation_envelope_is_carried_and_ignored_by_verification():
    signer, body = _fixture(attestation={"kind": "tee.example", "schema_version": 1, "payload": {"quote": "x"}})
    evidence = sign_inference_usage_evidence(body, signer)
    verified = _verify(evidence, signer, body)
    assert verified.attestation is not None
    assert verified.charge == 3500


def test_failed_request_evidence_carries_zero_charge():
    _, body = _fixture(outcome="failed")
    assert body.charge == 0


def test_evidence_on_an_eighteen_decimal_card_signs_and_round_trips():
    # 10**21 base units per million tokens is past 2**53-1: the card and the
    # charge travel as decimal text, so the body stays canonical and signable.
    rate_card = {**_RATE_CARD, "prompt_credits_per_million": 10**21, "completion_credits_per_million": 0}
    signer, body = _fixture(rate_card=rate_card, prompt_tokens=1_000_000, completion_tokens=0, charge=10**21)
    evidence = sign_inference_usage_evidence(body, signer)
    encoded = canonical_signed_usage_evidence(evidence)
    assert '"charge":"1000000000000000000000"' in encoded
    assert '"prompt_credits_per_million":"1000000000000000000000"' in encoded
    decoded = decode_signed_usage_evidence(encoded)
    assert decoded.body.charge == 10**21
    assert _verify(decoded, signer, body).rate_card.prompt_credits_per_million == 10**21
