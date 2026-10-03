"""Structural assertions about the built wheel.

These read the wheel archive directly: what modules it carries and what its
metadata requires. Nothing is installed, so they run in about a second. The
installation behaviour is asserted in test_distribution_install.py.
"""

from __future__ import annotations

from pathlib import Path

from conftest_wheels import INFERENCE, REPO, _members, _requirements, wheels

__all__ = ["wheels"]


def test_no_inference_project_declares_an_internal_editable_source() -> None:
    violations = [
        str(path.relative_to(REPO))
        for path in sorted(INFERENCE.glob("**/pyproject.toml"))
        if ".venv" not in path.parts and "[tool.uv.sources]" in path.read_text()
    ]
    assert violations == []


def test_domain_wheel_owns_every_module(wheels: dict[str, Path]) -> None:
    members = _members(wheels["domain"])
    assert {
        "arkhai_inference/__init__.py",
        "arkhai_inference/domain_runtime.py",
        "arkhai_inference/schema.py",
        "arkhai_inference/listings/__init__.py",
        "arkhai_inference/listings/identity.py",
        "arkhai_inference/listings/models.py",
        "arkhai_inference/listings/pricing.py",
        "arkhai_inference/negotiation/__init__.py",
        "arkhai_inference/negotiation/terms.py",
        "arkhai_inference/usage/__init__.py",
        "arkhai_inference/usage/evidence.py",
        "arkhai_inference/usage/models.py",
    } <= members
    assert not any(name.startswith("arkhai_inference/tests/") for name in members)
    assert not any(name.startswith("arkhai_inference/registry/") for name in members)


def test_domain_wheel_requires_versioned_core_and_identity(
    wheels: dict[str, Path],
) -> None:
    requirements = _requirements(wheels["domain"])
    for name in ("arkhai-core", "arkhai-kit-identity", "arkhai-kit-policy", "pydantic"):
        assert name in requirements, name
    for name in ("arkhai-core", "arkhai-kit-identity"):
        assert requirements[name], f"{name} is required without a version"
    assert not any(name.startswith("arkhai-apicredits") for name in requirements)
