"""The service starts only with both halves of its site identity, and refuses before it touches a database."""

from __future__ import annotations

import importlib
from base64 import urlsafe_b64encode
from pathlib import Path

import httpx
import pytest

from tests.integration.signed_service import (
    AUTHORITY_SEED,
    load_signed_app,
    unload_service_modules,
)


def _main(directory: Path, monkeypatch, *, credential: bool):
    (directory / "config.yml").write_text("")
    monkeypatch.setenv("CONFIG_DIRECTORY", str(directory))
    monkeypatch.setenv("INFERENCE_DATABASE_URL", f"sqlite:///{directory / 'inference.db'}")
    if credential:
        seed_file = directory / "site.ed25519"
        seed_file.write_bytes(urlsafe_b64encode(AUTHORITY_SEED).rstrip(b"=") + b"\n")
        monkeypatch.setenv("INFERENCE_SITE_SIGNING_KEY_FILE", str(seed_file))
    unload_service_modules()
    # Imported after the environment is set: configuration resolves at import.
    return importlib.import_module("inference_service.main")


@pytest.mark.parametrize("credential", [False, True], ids=["nothing", "credential-without-trust"])
async def test_a_service_missing_either_half_of_its_identity_refuses_to_start(tmp_path, monkeypatch, credential):
    try:
        main = _main(tmp_path, monkeypatch, credential=credential)
        with pytest.raises(main.MissingSiteIdentity, match="site_signing_key_file"):
            async with main.app.router.lifespan_context(main.app):
                pass
        assert not (tmp_path / "inference.db").exists()
    finally:
        unload_service_modules()


async def test_a_service_with_its_identity_starts_and_serves_health(tmp_path, monkeypatch):
    try:
        app = load_signed_app(tmp_path, monkeypatch)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://inference-service") as client:
                assert (await client.get("/health")).status_code == 200
        assert (tmp_path / "inference.db").exists()
    finally:
        unload_service_modules()
