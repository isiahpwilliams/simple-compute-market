"""The inference domain's issuance label, which its storefront and its authority both compose."""

from __future__ import annotations

from arkhai_api.labels import IssuanceLabel

#: Spells every schema string the family digests and signs for an inference
#: grant; its fulfilment prefix is the default, ``inference-fulfillment.v1``.
INFERENCE_LABEL = IssuanceLabel("inference")

__all__ = ["INFERENCE_LABEL"]
