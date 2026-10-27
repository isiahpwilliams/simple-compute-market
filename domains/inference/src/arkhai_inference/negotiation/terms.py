"""Inference binds the api family's purchase shape under ``inference.v1``.

``quantity`` is base units of the settlement asset to place on the key, since
one credit is one base unit.
"""

from arkhai_api.purchase import (
    PROVISION_TERMS_VERSION,
    provision_key_id,
    provision_key_mode,
    provision_quantity,
    provision_terms_model,
)

INFERENCE_PROVISION_KIND = "inference.v1"
INFERENCE_PROVISION_VERSION = PROVISION_TERMS_VERSION

InferenceProvisionTerms = provision_terms_model(INFERENCE_PROVISION_KIND)
make_inference_provision_terms = InferenceProvisionTerms.purchase

__all__ = [
    "INFERENCE_PROVISION_KIND",
    "INFERENCE_PROVISION_VERSION",
    "InferenceProvisionTerms",
    "make_inference_provision_terms",
    "provision_key_id",
    "provision_key_mode",
    "provision_quantity",
]
