from __future__ import annotations

import ast
import enum
from pathlib import Path

import pytest

ROUTER = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "LEITNER"
    / "src"
    / "leitner_learning"
    / "acp_agent"
    / "router.py"
)


class TaskClass(enum.Enum):
    SHORT_HINT = "short_hint"
    WORDING_REFINE = "wording_refine"
    JSON_EXTRACT = "json_extract"
    AGENT_CHAT = "agent_chat"


def _classify():
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "classify_task"
    )
    ns: dict = {"TaskClass": TaskClass}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ROUTER), "exec"), ns)
    return ns["classify_task"]


@pytest.fixture
def classify():
    return _classify()


def test_hint_word_does_not_steal_from_hinting(classify) -> None:
    assert classify("hinting at a refactor of the loader") is TaskClass.AGENT_CHAT


def test_hints_and_hint_still_route_short_hint(classify) -> None:
    assert classify("give me a hint") is TaskClass.SHORT_HINT
    assert classify("give me hints") is TaskClass.SHORT_HINT
    assert classify("one-liner please") is TaskClass.SHORT_HINT
