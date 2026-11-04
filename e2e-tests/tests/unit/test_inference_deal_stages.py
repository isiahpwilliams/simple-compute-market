"""The inference deal records each domain-neutral stage once, in order.

Read from source rather than collected, so the scenario is checked without its
lane's settings or services. The scenario is one test, as the API-credit deal
is, so each stage's bindings have one producer: its single ``complete`` call.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.e2e.roles.helpers.domain_deal import _STAGE_ORDER

SCENARIO = (
    Path(__file__).resolve().parents[1]
    / "e2e" / "roles" / "scenarios" / "inference" / "test_inference_deal_buyer_cli.py"
)


def _calls(name: str) -> list[ast.Call]:
    tree = ast.parse(SCENARIO.read_text(), filename=str(SCENARIO))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    ]
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def test_each_stage_is_completed_once_in_the_shared_order():
    stages = [
        call.args[0].attr
        for call in _calls("complete")
        if call.args and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name) and call.args[0].value.id == "DealStage"
    ]

    assert stages == [stage.name for stage in _STAGE_ORDER]


def test_the_deal_is_asserted_complete_after_its_last_stage():
    (asserted,) = _calls("assert_complete")
    last = _calls("complete")[-1]

    assert asserted.lineno > last.lineno
