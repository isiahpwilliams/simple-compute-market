"""A seller reprices between acceptance and fulfillment; the key carries the terms the buyer accepted.

The buyer negotiates, settles, and reads its result through the storefront's
typed client, and the seller reprices through its own. Beyond the storefront,
the chain is scripted at the Alkahest stage's injected escrow verifier and the
attestation client it is handed, and the inference authority at its HTTP
boundary; the quota site and registries are the other integration tests'.
Every key and address is a deterministic development value, never used on a
public network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx
from arkhai_api.issuance import accepted_terms_digest
from arkhai_api_selling.publish_route import ListingClient
from arkhai_inference.listings import InferenceModelCard, accepted_terms
from arkhai_inference.negotiation.terms import INFERENCE_PROVISION_KIND, INFERENCE_PROVISION_VERSION
from arkhai_inference.schema import InferenceMaterialization
from market_identity import Ed25519Signer, TrustedIdentitySet
from storefront_client import StorefrontClient
from storefront_client.settlement_routes import SETTLE

from inference_storefront import container, server
from inference_storefront.model_card import PublishFromQuotaRequest
from inference_storefront.services import credits_service_client
from tests.cards import model_card
from tests.integration.conftest import ADMIN_SIGNER, ESCROW, SELLER_SIGNER, QuotaSite, app
from tests.integration.issuance_authority import ESCROW_UID, ScriptedAuthority

BUYER_SIGNER = Ed25519Signer(bytes.fromhex("11" * 32))
BUYER_WALLET = "0x" + "55" * 20
ATTESTATION_UID = "0x" + "cd" * 32
QUANTITY = 40


class NegotiableQuotaSite(QuotaSite):
    """The quota site, also read through the client a negotiation's capacity guard holds."""

    def client(self) -> "NegotiableQuotaSite":
        return self

    def site(self, site_id: str) -> "NegotiableQuotaSite":
        return self.site_client(site_id)

    async def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "resource_id": rid,
                "resource_type": "inference",
                "available_units": units,
                "total_units": units,
                "state": "available",
            }
            for rid, units in self.units.items()
        ]


class ScriptedChain:
    """An escrow that verifies against the listing it is shown, and an attestation the chain records."""

    def __init__(self) -> None:
        self.verified_against: list[dict[str, Any]] = []
        self.attestations: list[str] = []
        self.client = SimpleNamespace(string_obligation=SimpleNamespace(do_obligation=self._attest))

    async def verify_escrow(self, *, listing: dict[str, Any], **_escrow: Any) -> int:
        self.verified_against.append(listing)
        return 0

    async def _attest(self, _data: str, condition_anchor: str) -> str:
        self.attestations.append(condition_anchor)
        return ATTESTATION_UID


@dataclass
class Parties:
    seller: StorefrontClient
    listings: ListingClient
    buyer: StorefrontClient
    admin: StorefrontClient
    public: StorefrontClient


@asynccontextmanager
async def running(monkeypatch, chain: ScriptedChain, authority: ScriptedAuthority) -> AsyncIterator[Parties]:
    """The app through its lifespan, over the scripted chain and authority."""

    async def no_startup_tasks(*, domain: Any) -> None:
        return None

    monkeypatch.setattr(server, "_startup_tasks", no_startup_tasks)
    quota = NegotiableQuotaSite({"svc-quota": 42})
    monkeypatch.setattr(container.QUOTA_CAPACITY, "runtime", lambda factory: quota)
    monkeypatch.setattr(server, "_build_alkahest_clients", lambda private_key: {"anvil": chain.client})
    monkeypatch.setattr(container.ALKAHEST_STAGE, "_verify_escrow", chain.verify_escrow)
    monkeypatch.setattr(credits_service_client, "_client", authority.client())
    served = app()
    async with served.router.lifespan_context(served):
        transport = httpx.ASGITransport(app=served)
        publishers = TrustedIdentitySet(identities=(SELLER_SIGNER.identity,))

        def signed(signer: Ed25519Signer, role: str) -> StorefrontClient:
            return StorefrontClient(
                "http://seller",
                signer=signer,
                caller_role=role,
                expected_publishers=publishers,
                transport=transport,
            )

        async with signed(SELLER_SIGNER, "seller") as seller, signed(
            BUYER_SIGNER, "buyer"
        ) as buyer, signed(ADMIN_SIGNER, "admin") as admin, StorefrontClient(
            "http://seller", transport=transport
        ) as public:
            yield Parties(
                seller=seller,
                listings=ListingClient(
                    seller, seller=SELLER_SIGNER.identity, request_model=PublishFromQuotaRequest
                ),
                buyer=buyer,
                admin=admin,
                public=public,
            )


def _publish_request(request_credits: int) -> dict[str, Any]:
    card = model_card()
    card["rate_card"] = {**card["rate_card"], "request_credits": request_credits}
    return {"resource_id": "svc-quota", "accepted_escrows": [dict(ESCROW)], "model_card": card}


async def test_the_key_is_issued_on_the_accepted_terms_after_the_seller_reprices(
    storefront, registries, monkeypatch
):
    chain = ScriptedChain()
    authority = ScriptedAuthority()
    async with running(monkeypatch, chain, authority) as parties:
        accepted_listing = await parties.public.get_listing(
            (await parties.listings.publish_from_quota(_publish_request(3))).listing_id
        )
        (release_condition,) = accepted_listing.extra["demands"]
        opened = await parties.buyer.negotiate_new(
            listing_id=accepted_listing.listing_id,
            initial_amount=QUANTITY,
            provision_terms={
                "kind": INFERENCE_PROVISION_KIND,
                "version": INFERENCE_PROVISION_VERSION,
                "payload": {"quantity": QUANTITY, "key": {"mode": "new"}},
            },
            proposal_fields={"token": ESCROW["literal_fields"]["token"]},
            chain_name="anvil",
            escrow_address=ESCROW["escrow_address"],
            escrow_expiration_unix=1_900_000_000,
            literal_fields=ESCROW["literal_fields"],
            rates=ESCROW["rates"],
            demands=[release_condition],
        )
        assert opened["action"] == "accept"

        # The seller reprices through its routes: it withdraws the accepted
        # listing and publishes its quota again at another rate. The stored
        # row of the accepted listing is then rewritten at the new rate too,
        # which no route does, so only the acceptance record still holds 3.
        await parties.seller.close_listing(accepted_listing.listing_id)
        repriced = await parties.public.get_listing(
            (await parties.listings.publish_from_quota(_publish_request(9))).listing_id
        )
        await container.resolved_sqlite_client.update_listing(
            listing_id=accepted_listing.listing_id,
            listing_resource={
                **accepted_listing.listing_resource,
                "rate_card": repriced.listing_resource["rate_card"],
            },
        )
        rewritten = await parties.public.get_listing(accepted_listing.listing_id)

        await parties.buyer.authenticated_request(
            "POST",
            SETTLE.path(ESCROW_UID),
            role=SETTLE.role,
            operation=SETTLE.operation,
            resource=ESCROW_UID,
            body={
                "negotiation_id": opened["negotiation_id"],
                "buyer_principal": BUYER_SIGNER.identity.model_dump(mode="json"),
                "buyer_evm_address": BUYER_WALLET,
                "chain_name": "anvil",
            },
        )
        settled = await parties.admin.wait_for_settlement(ESCROW_UID, timeout=10)
        status = await parties.buyer.get_settle_status(ESCROW_UID)

    assert (settled.ready, settled.status) == (True, "ready")
    assert repriced.listing_resource["rate_card"]["request_credits"] == "9"
    assert rewritten.listing_resource["rate_card"]["request_credits"] == "9"
    (verified,) = chain.verified_against
    assert verified["listing_resource"]["rate_card"]["request_credits"] == "3"
    (body,) = authority.requests
    terms = accepted_terms(InferenceModelCard.model_validate(accepted_listing.listing_resource))
    assert body["accepted_terms"] == terms
    assert body["terms_digest"] == accepted_terms_digest(terms)
    assert body["request_charge"] == 3
    assert body["quantity"] == QUANTITY
    assert chain.attestations == [ESCROW_UID]
    assert status.status == "ready"
    materialization = InferenceMaterialization.model_validate(
        status.tenant_credentials["materialization"]
    )
    assert materialization.rate_card.request_credits == 3
    assert materialization.listing_resource.model_dump(mode="json") == accepted_listing.listing_resource
