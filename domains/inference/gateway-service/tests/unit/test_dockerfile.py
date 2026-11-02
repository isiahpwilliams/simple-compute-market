"""The gateway image builds from digest-pinned bases."""

from __future__ import annotations

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def test_every_base_is_pinned_to_a_digest():
    bases = [line for line in DOCKERFILE.read_text().splitlines() if line.startswith("FROM ")]

    assert bases
    assert all(re.search(r"@sha256:[0-9a-f]{64}\b", line) for line in bases), bases
