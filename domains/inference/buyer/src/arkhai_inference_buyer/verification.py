"""Purchase-time verification hook, run on a listing's attestation envelope before any settlement is proposed.

Both the Alkahest stage and its buy session are subclassed because they are the
two places the buying library proposes from. No proof format is defined here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

import typer
from arkhai_api_buying.stages import BuyRequest
from arkhai_api_buying_alkahest.stage import AlkahestBuyerStage, AlkahestBuySession
from arkhai_inference.listings import coerce_resource_dict


class PurchaseVerificationHook(Protocol):
    """Returns why the listing may not be bought, or ``None`` to admit it."""

    def __call__(self, attestation: Mapping[str, Any] | None) -> str | None: ...


def admit_all(attestation: Mapping[str, Any] | None) -> str | None:
    return None


def listing_refusal(listing: Mapping[str, Any], verify: PurchaseVerificationHook) -> str | None:
    attestation = coerce_resource_dict(listing.get("listing_resource")).get("attestation")
    return verify(attestation if isinstance(attestation, Mapping) else None)


class VerifyingAlkahestStage(AlkahestBuyerStage):
    """The Alkahest buyer stage with the purchase-time hook before each proposal."""

    def __init__(self, *, verify: PurchaseVerificationHook = admit_all, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.verify = verify

    def prepare_selection(self, selected: Any, *, listing: Any, **kwargs: Any) -> Any:
        refusal = listing_refusal(listing, self.verify)
        if refusal is not None:
            raise ValueError(f"listing {listing.get('listing_id')!r} refused before settlement: {refusal}")
        return super().prepare_selection(selected, listing=listing, **kwargs)

    def open_buy(self, request: BuyRequest) -> AlkahestBuySession:
        return _VerifyingBuySession(self, request)


class _VerifyingBuySession(AlkahestBuySession):
    def __init__(self, stage: VerifyingAlkahestStage, request: BuyRequest) -> None:
        super().__init__(stage, request)
        self._verify = stage.verify

    def propose(self, listing: Mapping[str, Any], *, expiration_unix: int) -> Any | None:
        refusal = listing_refusal(listing, self._verify)
        if refusal is not None:
            # Skip it like a listing with no compatible settlement; another match may still be bought.
            typer.secho(
                f"listing {listing.get('listing_id')!r} refused before settlement: {refusal}",
                err=True,
                fg=typer.colors.YELLOW,
            )
            return None
        return super().propose(listing, expiration_unix=expiration_unix)
