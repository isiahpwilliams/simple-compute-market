"""Inference round-zero provision intent."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from domains.inference.negotiation.terms import (
    INFERENCE_PROVISION_KIND,
    InferenceProvisionTerms,
    make_inference_provision_terms,
    provision_key_id,
    provision_key_mode,
    provision_quantity,
)


def test_new_key_intent_defaults():
    terms = make_inference_provision_terms(quantity=2_000_000)
    assert terms.kind == INFERENCE_PROVISION_KIND
    assert terms.version == 1
    assert terms.quantity == 2_000_000
    assert terms.key_mode == "new"
    assert terms.key_id is None
    assert terms.payload == {"quantity": 2_000_000, "key": {"mode": "new"}}


def test_existing_key_intent_carries_key_id():
    terms = make_inference_provision_terms(quantity=5, key_mode="existing", key_id="ak_1")
    assert terms.key_mode == "existing"
    assert terms.key_id == "ak_1"


@pytest.mark.parametrize("quantity", [0, -1])
def test_quantity_below_one_is_rejected(quantity):
    with pytest.raises(ValidationError):
        make_inference_provision_terms(quantity=quantity)


def test_existing_key_without_id_is_rejected():
    with pytest.raises(ValidationError):
        make_inference_provision_terms(quantity=1, key_mode="existing")


@pytest.mark.parametrize(
    "envelope",
    [
        {"kind": "api_credits.v1", "version": 1, "payload": {"quantity": 1}},
        {"kind": "inference.v1", "version": 2, "payload": {"quantity": 1}},
        {"kind": "inference.v1", "version": 1, "payload": {"quantity": 1, "extra": 1}},
    ],
)
def test_wrong_kind_version_or_payload_is_rejected(envelope):
    with pytest.raises(ValidationError):
        InferenceProvisionTerms.model_validate(envelope)


def test_accessors_read_any_carrier():
    wire = {"kind": "inference.v1", "version": 1, "payload": {"quantity": "7", "key": {"mode": "existing", "key_id": "ak_2"}}}
    assert provision_quantity(wire) == 7
    assert provision_key_mode(wire) == "existing"
    assert provision_key_id(wire) == "ak_2"
    assert provision_quantity({"payload": {"quantity": "x"}}) is None
    assert provision_key_mode({}) == "new"
    assert provision_key_id(object()) is None
