"""Installation behaviour of the built wheel.

Installs the wheel into a throwaway environment and imports the contract
from it, which is the condition the Docker runtime stages run under: no
source tree on the path. An in-process import proves nothing about the
wheel because this interpreter already has the source importable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest_wheels import wheels

__all__ = ["wheels"]


def test_domain_contract_imports_from_built_wheel(
    wheels: dict[str, Path],
) -> None:
    venv = wheels["domain"].parent / "venv"
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(venv)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--find-links",
            str(wheels["domain"].parent),
            str(wheels["domain"]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    code = """
from pathlib import Path
from arkhai_inference import domain_runtime
from arkhai_inference.listings import derive_model_id
from arkhai_inference.usage import derive_charge
contract = domain_runtime.market_domain()
module_path = Path(domain_runtime.__file__).resolve()
assert contract.identity == "inference.v1"
assert derive_model_id("Meta-Llama", "Llama-3.1-8B-Instruct") == "meta-llama/llama-3.1-8b-instruct"
assert "site-packages" in module_path.parts
"""
    subprocess.run(
        [str(python), "-I", "-c", code],
        cwd=wheels["domain"].parent,
        check=True,
        capture_output=True,
        text=True,
    )
