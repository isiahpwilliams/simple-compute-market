"""The inference domain's issuance label, which its storefront and its authority both compose."""

from __future__ import annotations

from arkhai_api.labels import IssuanceLabel

#: Spells every schema string digested and signed for an inference grant.
INFERENCE_LABEL = IssuanceLabel("inference")

__all__ = ["INFERENCE_LABEL"]
