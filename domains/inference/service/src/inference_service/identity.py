"""This service's site-authority identity: `market_site.identity` fed from this service's configuration.

Resolved at import, so an unreadable credential, or one not owning the pinned
principal, fails at startup rather than on the first request.
"""

from __future__ import annotations

from pathlib import Path

from inference_service.config import settings
from market_site.identity import SiteIdentity, parse_principal

_pinned_principal = settings.get("site_principal", "") or None

# Read directly, not through the owner-only secret-file provider: service
# credentials here are read-only bind mounts of committed, world-readable files
# (git does not carry `0600`), which that provider would refuse.
_credential_file = str(settings.get("site_signing_key_file", "") or "")
_credential = (
    Path(_credential_file).read_bytes() if _credential_file else None
)

site_identity = SiteIdentity(
    credential=_credential,
    trusted_principals=settings.get("trusted_principals", None),
    expected_principal=(
        parse_principal(_pinned_principal) if _pinned_principal else None
    ),
)


def signed_authentication_enabled() -> bool:
    """Whether this deployment can verify callers and sign its own responses."""
    return site_identity.enabled


def require_signer():
    return site_identity.require_signer()


def expected_principals(role: str):
    return site_identity.expected_principals(role)
