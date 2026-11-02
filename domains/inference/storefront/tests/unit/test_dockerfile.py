"""The image's listener and health check follow its port setting."""

from __future__ import annotations

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"
VARIABLE = "PORT"


def _instruction(name: str) -> str:
    text = DOCKERFILE.read_text().replace("\\\n", " ")
    lines = [line for line in text.splitlines() if line.startswith(name + " ")]
    assert len(lines) == 1, lines
    return lines[0]


def test_the_port_variable_is_set_from_the_build_argument():
    assert re.search(rf"^ENV {VARIABLE}=\$\{{PORT\}}$", DOCKERFILE.read_text(), re.MULTILINE)


def test_the_listener_and_health_check_read_the_port_variable():
    for name in ("CMD", "HEALTHCHECK"):
        instruction = _instruction(name)
        assert VARIABLE in instruction, name
        assert not re.search(r"(--port\W+|localhost:)\d", instruction), instruction
