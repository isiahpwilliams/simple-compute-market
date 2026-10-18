"""The inference materialization: the rate card pinned at acceptance, delivered with the key."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Mapping, MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arkhai_inference.listings import InferenceModelCard, InferenceRateCard, coerce_resource_dict
from arkhai_inference.schema import InferenceMaterialization
from core_storefront.domain_registry import StorefrontDomainRegistry
from market_core import MarketDomainContract

from inference_storefront.listing_binding import inference_registration

ARTIFACT_SLOT = "materialization"
PUBLIC_RESULT_KEY = "materialization"


class PinnedRateCardConflict(RuntimeError):
    """A negotiation's pinned rate card, or its materialization, was reused with changed data."""


def migrate_accepted_rate_cards(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inference_accepted_rate_cards (
          negotiation_id TEXT PRIMARY KEY,
          rate_card TEXT NOT NULL,
          accepted_at TEXT NOT NULL
        )
        """
    )


class AcceptedRateCardRepository:
    """The rate card in force when each negotiation was accepted."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def store(self, *, negotiation_id: str, rate_card: InferenceRateCard) -> None:
        encoded = rate_card.model_dump_json()
        connection = sqlite3.connect(self._db_path, timeout=30)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT rate_card FROM inference_accepted_rate_cards WHERE negotiation_id = ?",
                (negotiation_id,),
            ).fetchone()
            if existing is not None:
                if InferenceRateCard.model_validate_json(existing[0]) != rate_card:
                    raise PinnedRateCardConflict(
                        f"negotiation {negotiation_id!r} already pinned a different rate card"
                    )
                connection.commit()
                return
            connection.execute(
                "INSERT INTO inference_accepted_rate_cards (negotiation_id, rate_card, accepted_at) "
                "VALUES (?, ?, ?)",
                (negotiation_id, encoded, datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
        finally:
            connection.close()

    def load(self, negotiation_id: str) -> InferenceRateCard | None:
        connection = sqlite3.connect(self._db_path, timeout=30)
        try:
            row = connection.execute(
                "SELECT rate_card FROM inference_accepted_rate_cards WHERE negotiation_id = ?",
                (negotiation_id,),
            ).fetchone()
        finally:
            connection.close()
        return InferenceRateCard.model_validate_json(row[0]) if row else None


async def record_accepted_rate_card(repository: Any, acceptance: Any) -> None:
    """Pin the listing's rate card as stored at acceptance; the artifact store needs the thread bound."""
    await repository.copy_listing_binding_to_thread(
        negotiation_id=acceptance.negotiation_id,
        listing_id=acceptance.listing_id,
    )
    card = InferenceModelCard.model_validate(
        coerce_resource_dict(acceptance.listing_record.get("listing_resource"))
    )
    await asyncio.to_thread(
        AcceptedRateCardRepository(repository.db_path).store,
        negotiation_id=acceptance.negotiation_id,
        rate_card=card.rate_card,
    )


async def pinned_rate_card(repository: Any, negotiation_id: str) -> InferenceRateCard:
    card = await asyncio.to_thread(AcceptedRateCardRepository(repository.db_path).load, negotiation_id)
    if card is None:
        raise RuntimeError(f"negotiation {negotiation_id!r} pinned no rate card at acceptance")
    return card


def _registry(domain: MarketDomainContract) -> StorefrontDomainRegistry:
    return StorefrontDomainRegistry((inference_registration(domain),))


async def store_materialization(
    repository: Any,
    *,
    domain: MarketDomainContract,
    negotiation_id: str,
    materialization: InferenceMaterialization,
) -> InferenceMaterialization:
    """Record the materialization once; a retry must find the same one."""
    registry = _registry(domain)
    recorded = await repository.load_domain_artifact(
        negotiation_id=negotiation_id,
        artifact_slot=ARTIFACT_SLOT,
        registry=registry,
    )
    if recorded is None:
        await repository.save_domain_artifact(
            negotiation_id=negotiation_id,
            artifact_slot=ARTIFACT_SLOT,
            value=materialization,
            registry=registry,
        )
        return materialization
    if recorded != materialization:
        raise PinnedRateCardConflict(
            f"negotiation {negotiation_id!r} already materialized differently"
        )
    return recorded


def attach_materialization(result: MutableMapping[str, Any], materialization: InferenceMaterialization) -> None:
    result[PUBLIC_RESULT_KEY] = materialization.model_dump(mode="json", exclude_none=True)


async def deliver_materialization(
    repository: Any,
    *,
    domain: MarketDomainContract,
    negotiation_id: str,
    escrow_uid: str,
    quantity: int,
    issuance: Any,
    rate_card: InferenceRateCard,
    mechanism: str,
    result: MutableMapping[str, Any],
) -> None:
    """Record the delivered materialization once and attach it to the delivery result."""
    materialization = InferenceMaterialization(
        escrow_uid=escrow_uid,
        quantity=quantity,
        key_mode=issuance.key_mode,
        key_id=issuance.key_id,
        rate_card=rate_card,
        fulfillment_id=issuance.fulfillment_id,
        mechanism=mechanism,
    )
    attach_materialization(
        result,
        await store_materialization(
            repository, domain=domain, negotiation_id=negotiation_id, materialization=materialization
        ),
    )


def public_materialization(result: Mapping[str, Any]) -> dict[str, Any]:
    value = result.get(PUBLIC_RESULT_KEY)
    return {PUBLIC_RESULT_KEY: value} if value else {}
