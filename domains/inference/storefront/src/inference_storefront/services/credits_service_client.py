"""Storefront-owned composition of the family authority client."""

from __future__ import annotations

from arkhai_api_client import AuthorityClient
from arkhai_inference.label import INFERENCE_LABEL

from inference_storefront.utils import config

_client: AuthorityClient | None = None


def get_credits_service_client() -> AuthorityClient:
    """Return the process-wide client for the configured inference authority.

    Signing is enabled only with a configured authority trust set: signing
    requests without verifying responses would accept an unauthenticated
    answer, and the client refuses that combination.
    """
    global _client
    if _client is None:
        authorities = config.credits_expected_authorities()
        _client = AuthorityClient(
            config.credits_service_url(),
            config.credits_admin_key(),
            label=INFERENCE_LABEL,
            signer=config.resolve_identity_signer() if authorities else None,
            expected_authorities=authorities,
        )
    return _client
