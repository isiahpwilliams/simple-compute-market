"""The purchase-time hook runs before the Alkahest stage proposes; the library's methods are replaced by recorders."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from arkhai_api_buying.stages import BuyRequest
from arkhai_api_buying_alkahest.stage import AlkahestBuyerStage, AlkahestBuySession

from arkhai_inference_buyer.verification import VerifyingAlkahestStage, admit_all

ENVELOPE = {"kind": "example-proof", "schema_version": 1, "payload": {"claim": "x"}}
LISTING = {"listing_id": "lst-1", "listing_resource": {"model_id": "arkhai/stub", "attestation": ENVELOPE}}
PROPOSAL = object()


@pytest.fixture
def library(monkeypatch):
    calls: list[str] = []

    def propose(self, listing, *, expiration_unix):
        calls.append("propose")
        return PROPOSAL

    def prepare_selection(self, selected, *, listing, **kwargs):
        calls.append("prepare_selection")
        return selected

    monkeypatch.setattr(AlkahestBuySession, "propose", propose)
    monkeypatch.setattr(AlkahestBuyerStage, "prepare_selection", prepare_selection)
    return calls


def _request() -> BuyRequest:
    return BuyRequest(
        identity=None, settlement=None, policy=None, enabled=True,
        options=SimpleNamespace(), assume_yes=True, console=None,
    )


def _recording_hook(answer):
    seen: list = []

    def hook(attestation):
        seen.append(attestation)
        return answer

    return hook, seen


def test_the_hook_sees_the_listings_envelope_before_the_proposal(library):
    hook, seen = _recording_hook(None)
    session = VerifyingAlkahestStage(verify=hook).open_buy(_request())

    assert session.propose(LISTING, expiration_unix=1) is PROPOSAL
    assert seen == [ENVELOPE]
    assert library == ["propose"]


def test_a_refusal_stops_the_proposal_and_names_the_listing(library, capsys):
    hook, _seen = _recording_hook("proof does not verify")
    stage = VerifyingAlkahestStage(verify=hook)

    assert stage.open_buy(_request()).propose(LISTING, expiration_unix=1) is None
    assert "'lst-1' refused before settlement: proof does not verify" in capsys.readouterr().err
    with pytest.raises(ValueError, match="proof does not verify"):
        stage.prepare_selection(object(), listing=LISTING, settlement_policy=None)
    assert library == []


def test_a_listing_without_an_envelope_reaches_the_hook_as_none(library):
    hook, seen = _recording_hook(None)
    VerifyingAlkahestStage(verify=hook).open_buy(_request()).propose(
        {"listing_id": "lst-2", "listing_resource": {"model_id": "arkhai/stub"}}, expiration_unix=1
    )
    assert seen == [None]


def test_the_default_admits_an_envelope_no_proof_format_reads(library):
    malformed = {"listing_id": "lst-3", "listing_resource": {"attestation": {"kind": ""}}}
    assert VerifyingAlkahestStage().open_buy(_request()).propose(malformed, expiration_unix=1) is PROPOSAL
    assert library == ["propose"]


def test_the_default_admits_so_the_stage_behaves_as_the_unwrapped_one(library):
    stage = VerifyingAlkahestStage()
    assert stage.verify is admit_all
    selected = object()

    assert stage.open_buy(_request()).propose(LISTING, expiration_unix=1) is PROPOSAL
    assert stage.prepare_selection(selected, listing=LISTING, settlement_policy=None) is selected
    assert library == ["propose", "prepare_selection"]
