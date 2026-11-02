"""The storefront imports no sibling domain or other settlement mechanism.

Modules are parsed rather than imported so ``TYPE_CHECKING`` and local imports count.
"""

from __future__ import annotations

import ast
from pathlib import Path

import inference_storefront

_FORBIDDEN = ("arkhai_apicredits", "apicredits_", "arkhai_api_selling_arkhai_payments", "market_arkhai_payments")


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            modules.add(node.module)
    return modules


def test_no_module_imports_api_credits_or_fiat_payments() -> None:
    root = Path(inference_storefront.__file__).parent
    offending = {
        f"{path.relative_to(root)}: {module}"
        for path in root.rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith(_FORBIDDEN)
    }

    assert not offending
