"""Model identifier derivation.

Sellers of the same weights converge on one ``model_id`` by deriving it from
the upstream owner and repository name: lowercased, with revision, branch, and
quantization suffixes stripped. Private weights use the owner's namespace and
a fine-tune the fine-tuner's; the caller supplies that owner. The card does
not require the rule; a registry operator may.
"""

from __future__ import annotations

import re

from arkhai_inference.listings.models import QUANTIZATIONS

_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_SOURCE_PREFIX = re.compile(r"^(?:hf://|https?://huggingface\.co/)", re.IGNORECASE)
_QUANTIZATION_SUFFIX = re.compile(
    r"-(?:%s)$" % "|".join(q for q in QUANTIZATIONS if q != "none")
)


def _segment(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if not _SEGMENT.fullmatch(normalized):
        raise ValueError(f"{field} must be a single owner or repository name")
    return normalized


def derive_model_id(owner: str, name: str) -> str:
    """Canonical ``<owner>/<name>`` for one set of weights."""
    owner = _segment(owner, "owner")
    name = _segment(name, "name")
    while True:
        stripped = _QUANTIZATION_SUFFIX.sub("", name)
        if stripped == name:
            break
        name = stripped
    if not name:
        raise ValueError("name must not be only a quantization suffix")
    return f"{owner}/{name}"


def model_id_from_artifact_ref(artifact_ref: str) -> str:
    """Derive from a source reference such as ``hf://owner/Name@revision``."""
    ref = _SOURCE_PREFIX.sub("", artifact_ref.strip())
    ref = ref.split("@", 1)[0].split("#", 1)[0]
    parts = [part for part in ref.split("/") if part]
    if "tree" in parts:
        parts = parts[: parts.index("tree")]
    if len(parts) < 2:
        raise ValueError("artifact_ref must carry an owner and a repository name")
    owner, name = parts[0], parts[1].split(":", 1)[0]
    return derive_model_id(owner, name)
