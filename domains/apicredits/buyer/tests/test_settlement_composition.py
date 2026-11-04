"""The plugin composes the Alkahest and payments entries into one buyer stage table."""

from market_alkahest.schemas import EscrowProposal
from market_arkhai_payments import ARKHAI_PAYMENTS_MECHANISM
from market_core.schemas import SettlementSelection
from market_identity import Ed25519Signer

from arkhai_apicredits_buyer.cli import SETTLEMENT


def test_payments_only_registry_resolution_does_not_resolve_wallet(monkeypatch) -> None:
    """A wallet-free buyer is never asked for an EVM wallet."""
    monkeypatch.setattr(
        "arkhai_api_buying_alkahest.stage.resolve_buyer_wallet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("payments-only policy resolved wallet")
        ),
    )
    payments = {
        "enabled": True,
        "service_url": "https://payments.example",
        "service_identity": Ed25519Signer(bytes(range(32))).identity.model_dump(mode="json"),
        "fee_bps": 250,
        "dispute_authority": "33333333-3333-4333-8333-333333333333",
        "api_key_env": "ARKHAI_PAYMENTS_API_KEY",
    }

    policy = SETTLEMENT.resolve_policy(
        {
            "Settlement": {
                "schema_version": 1,
                "priority": ["arkhai.payments.v1"],
                "arkhai_payments": payments,
            }
        }
    )

    assert [item.mechanism_id for item in policy.ordered_registrations()] == [
        "arkhai.payments.v1"
    ]


_DEMANDS = [{
    "chain_name": "anvil", "arbiter": "0x" + "cc" * 20,
    "demand_data": {"recipient": "0x" + "dd" * 20},
}]


def test_an_escrow_proposal_records_its_listings_release_conditions() -> None:
    proposal = EscrowProposal(
        chain_name="anvil", escrow_address="0x" + "aa" * 20,
        literal_fields={"token": "0x" + "bb" * 20}, expiration_unix=1_800_000_000,
    )

    assert SETTLEMENT.accepted_listing_record({"demands": _DEMANDS}, proposal) == {
        "release_conditions": _DEMANDS
    }


def test_a_payment_selection_records_nothing_about_its_listing() -> None:
    selection = SettlementSelection(
        mechanism=ARKHAI_PAYMENTS_MECHANISM, option_id="a" * 64,
        expiration_unix=1_800_000_000,
    )

    assert SETTLEMENT.accepted_listing_record({"demands": _DEMANDS}, selection) == {}


def test_buyer_registry_installs_alkahest_and_payments() -> None:
    assert {
        item.mechanism_id for item in SETTLEMENT.registry().registrations
    } == {
        "alkahest.v1",
        "arkhai.payments.v1",
    }
