"""The inference service composed with signed authentication, in process; its modules resolve configuration at import."""

from __future__ import annotations

import importlib
import json
import sys
from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Any

from market_identity import Ed25519Signer

# Deterministic development seeds for these tests only; never used on any network.
AUTHORITY_SEED = b"inference-authority-seed-32byte!"
AUTHORITY = Ed25519Signer(AUTHORITY_SEED)
STOREFRONT_SIGNER = Ed25519Signer(b"inference-storefront-seed-32-by!")
GATEWAY_SIGNER = Ed25519Signer(b"inference-gateway-seed-32-bytes!")

_MODULES = (
    "inference_service.main",
    "inference_service.identity",
    "inference_service.config",
    "inference_service.container",
)


def load_authority(directory: Path, monkeypatch) -> Any:
    """The service trusting the storefront as ``seller`` and the gateway as ``service``."""
    seed_file = directory / "site.ed25519"
    seed_file.write_bytes(urlsafe_b64encode(AUTHORITY_SEED).rstrip(b"=") + b"\n")
    (directory / "config.yml").write_text("")
    monkeypatch.setenv("CONFIG_DIRECTORY", str(directory))
    monkeypatch.setenv("INFERENCE_DATABASE_URL", f"sqlite:///{directory / 'inference.db'}")
    monkeypatch.setenv("INFERENCE_SITE_SIGNING_KEY_FILE", str(seed_file))
    monkeypatch.setenv(
        "INFERENCE_TRUSTED_PRINCIPALS",
        "@json "
        + json.dumps(
            {
                "seller": [STOREFRONT_SIGNER.identity.model_dump(mode="json")],
                "service": [GATEWAY_SIGNER.identity.model_dump(mode="json")],
            }
        ),
    )
    unload_authority()
    main = importlib.import_module("inference_service.main")
    importlib.import_module("inference_service.container").init()
    return main.app


def unload_authority() -> None:
    for name in _MODULES:
        sys.modules.pop(name, None)
