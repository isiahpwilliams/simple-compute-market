"""Inference concept modules: reconciler and guards."""

from __future__ import annotations

from market_identity import Ed25519Signer, Identity, IdentityScheme

from arkhai_inference.listings.reconciler import (
    CreditListingSource,
    listing_quota_resource_id,
    reopenable_credit_listing_ids,
    stale_open_credit_listing_ids,
)
from arkhai_inference.negotiation.policies import (
    key_owned_by_buyer_principal,
    credit_quota_guard,
)

from market_policy.negotiation_middleware import (
    NegotiationContext,
    NegotiationRound,
)

_TOKEN = "0x" + "01" * 20
_ESCROW = "0x" + "11" * 20
_BUYER = "0x" + "ab" * 20
_BUYER_PRINCIPAL = Identity(
    scheme=IdentityScheme.EIP191,
    identifier=_BUYER,
)
_ED25519_PRINCIPAL = Ed25519Signer(bytes.fromhex("22" * 32)).identity


def _offer(resource_id="svc-quota"):
    return {
        "kind": "inference.v1",
        "model_id": "acme/atlas-7b",
        "artifact_ref": "hf://acme/Atlas-7B@main",
        "provenance": "self-hosted",
        "served_model_name": "atlas-7b",
        "context_length": 8192,
        "quantization": "none",
        "architecture": {"modality": "text->text"},
        "supported_parameters": ["tools"],
        "endpoint": {"base_url": "https://api.acme.example/v1"},
        "rate_card": {"prompt_credits_per_million": 0, "completion_credits_per_million": 0, "request_credits": 1},
        "resource_id": resource_id,
        "capacity_site_id": "tokens",
        "offering_mode": "inference",
    }


def _listing(resource_id="svc-quota", rate="1"):
    return {
        "listing_id": "L-tok",
        "status": "open",
        "listing_resource": _offer(resource_id),
        "accepted_escrows": [{
            "chain_name": "anvil",
            "escrow_address": _ESCROW,
            "literal_fields": {"token": _TOKEN},
            "rates": [{"field": "amount", "per": "credit", "value": rate}],
        }],
    }


def _round0(proposal):
    return [NegotiationRound(
        round_number=0, sender="them", action="initial", proposal=proposal,
    )]


def _proposal(amount=300):
    return {
        "chain_name": "anvil",
        "escrow_address": _ESCROW,
        "fields": {"token": _TOKEN, "amount": amount},
        "literal_fields": {"token": _TOKEN},
        "rates": [{"field": "amount", "per": "credit", "value": "1"}],
        "expiration_unix": 1_800_000_000,
    }


def _context(listing=None, *, resources=None, **intermediate):
    return NegotiationContext(
        direction="maximize",
        our_reference_amount=300.0,
        listing=listing or _listing(),
        available_resources={"resources": resources or []},
        intermediate=intermediate,
    )


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------

def _source(listing_id, resource_id, status, closed_by=None):
    # Site and quota resource come from the listing's binding.
    return CreditListingSource(listing_id, status, closed_by, "tokens", resource_id)


def _backed(_source, available):
    return available()


def _unbacked(_source, available):
    return None


def test_reconciler_close_on_exhaustion_and_reopen():
    sources = [
        _source("L-a", "svc-a", "open"),
        _source("L-b", "svc-b", "open"),
        _source("L-c", "svc-a", "closed", "reconciliation"),
    ]
    judge = _backed
    availability = {("tokens", "svc-a"): 0, ("tokens", "svc-b"): 12}
    assert stale_open_credit_listing_ids(sources, availability=availability, judge=judge) == ["L-a"]
    assert reopenable_credit_listing_ids(sources, availability=availability, judge=judge) == []

    availability = {("tokens", "svc-a"): 3, ("tokens", "svc-b"): 12}
    assert stale_open_credit_listing_ids(sources, availability=availability, judge=judge) == []
    assert reopenable_credit_listing_ids(sources, availability=availability, judge=judge) == ["L-c"]


def test_reconciler_reopens_only_what_reconciliation_closed():
    sources = [
        _source("L-seller", "svc-a", "closed", "seller"),
        _source("L-quota", "svc-a", "closed", "reconciliation"),
    ]
    availability = {("tokens", "svc-a"): 5}
    assert reopenable_credit_listing_ids(
        sources, availability=availability, judge=_backed
    ) == ["L-quota"]


def test_reconciler_unknown_availability_is_conservative():
    sources = [_source("L-a", "svc-a", "open")]
    judge = _backed
    # Authority unreachable: close nothing, reopen nothing.
    assert stale_open_credit_listing_ids(sources, availability=None, judge=judge) == []
    assert reopenable_credit_listing_ids(sources, availability=None, judge=judge) == []
    # Resource gone from the ledger: the listing must not stay open.
    assert stale_open_credit_listing_ids(sources, availability={}, judge=judge) == ["L-a"]


def test_availability_closes_no_listing_its_backing_does_not_bound():
    sources = [_source("L-a", "svc-a", "open")]

    assert stale_open_credit_listing_ids(
        sources, availability={}, judge=_unbacked
    ) == []


def test_a_non_inference_listing_names_no_quota_resource():
    assert listing_quota_resource_id({"listing_resource": {"gpu_model": "H200"}}) is None


# ---------------------------------------------------------------------------
# Quota guard
# ---------------------------------------------------------------------------

def test_quota_guard_passes_when_covered_and_rejects_when_not():
    resources = [{"resource_id": "svc-quota", "available_units": 5}]
    decision, _ = credit_quota_guard(
        _round0(_proposal()),
        _context(resources=resources, requested_quantity=5),
    )
    assert decision is None

    decision, _ = credit_quota_guard(
        _round0(_proposal()),
        _context(resources=resources, requested_quantity=6),
    )
    assert decision.action == "reject"
    assert decision.reason.startswith("quota_exhausted")


def test_quota_guard_is_not_applicable_without_a_snapshot():
    # The storefront captures no snapshot for a listing availability does not
    # bound; the guard then neither passes nor rejects on quota.
    context = NegotiationContext(
        direction="maximize",
        our_reference_amount=300.0,
        listing=_listing(),
        available_resources={},
        intermediate={"requested_quantity": 1_000_000},
    )

    decision, _ = credit_quota_guard(_round0(_proposal()), context)

    assert decision is None


def test_quota_guard_matches_by_resource_id():
    resources = [
        {"resource_id": "other", "available_units": 100},
        {"resource_id": "svc-quota", "available_units": 2},
    ]
    decision, _ = credit_quota_guard(
        _round0(_proposal()),
        _context(resources=resources, requested_quantity=3),
    )
    assert decision.action == "reject"


def test_quota_guard_ignores_non_inference_listings():
    decision, _ = credit_quota_guard(
        _round0(_proposal()),
        _context(listing={"listing_resource": {"gpu_model": "H200"}},
                 requested_quantity=3),
    )
    assert decision is None


# ---------------------------------------------------------------------------
# Ownership guard
# ---------------------------------------------------------------------------

def _owned_record(
    owner=_BUYER_PRINCIPAL.identifier,
    scheme=IdentityScheme.EIP191.value,
    status="active",
):
    return {
        "key_id": "ik_x",
        "owner_scheme": scheme,
        "owner_id": owner,
        "status": status,
    }


def test_ownership_guard_passes_new_key_deals():
    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()), _context(key_mode="new"),
    )
    assert decision is None


def test_ownership_guard_admits_same_canonical_principal():
    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()),
        _context(
            key_mode="existing", key_id="ik_x",
            key_record=_owned_record(owner=_BUYER.upper().replace("0X", "0x")),
            buyer_principal=_BUYER_PRINCIPAL,
        ),
    )
    assert decision is None


def test_ownership_guard_rejects_stranger():
    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()),
        _context(
            key_mode="existing", key_id="ik_x",
            key_record=_owned_record(),
            buyer_principal=Identity(
                scheme=IdentityScheme.EIP191,
                identifier="0x" + "99" * 20,
            ),
        ),
    )
    assert decision.action == "reject"
    assert decision.reason.startswith("key_not_owned")


def test_ownership_guard_rejects_unknown_and_revoked_keys():
    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()),
        _context(
            key_mode="existing",
            key_id="ik_x",
            key_record=None,
            buyer_principal=_BUYER_PRINCIPAL,
        ),
    )
    assert decision.reason.startswith("key_not_found")

    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()),
        _context(
            key_mode="existing", key_id="ik_x",
            key_record=_owned_record(status="revoked"),
            buyer_principal=_BUYER_PRINCIPAL,
        ),
    )
    assert decision.reason.startswith("key_revoked")


def test_ownership_guard_open_key_admits_anyone():
    record = {
        "key_id": "ik_x",
        "owner_scheme": None,
        "owner_id": None,
        "status": "active",
    }
    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()),
        _context(
            key_mode="existing",
            key_id="ik_x",
            key_record=record,
            buyer_principal=_ED25519_PRINCIPAL,
        ),
    )
    assert decision is None


def test_ownership_guard_rejects_cross_scheme_collision():
    decision, _ = key_owned_by_buyer_principal(
        _round0(_proposal()),
        _context(
            key_mode="existing",
            key_id="ik_x",
            key_record=_owned_record(
                scheme=IdentityScheme.ED25519.value,
                owner=_ED25519_PRINCIPAL.identifier,
            ),
            buyer_principal=_BUYER_PRINCIPAL,
        ),
    )
    assert decision.action == "reject"
    assert decision.reason.startswith("key_not_owned")
