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


def _warm_dream_fn() -> ast.FunctionDef:
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TurnRouter")
    return next(
        item
        for item in cls.body
        if isinstance(item, ast.FunctionDef) and item.name == "warm_dream"
    )


def test_warm_dream_load_does_not_hold_the_backend_create_lock() -> None:
    """generate() splits create vs infer locks so a torch load cannot deadlock the next prompt."""

    class Walk(ast.NodeVisitor):
        def __init__(self) -> None:
            self._backend_depth = 0
            self.load_under_backend = False

        def visit_With(self, node: ast.With) -> None:
            backend = any(
                isinstance(item.context_expr, ast.Attribute)
                and item.context_expr.attr == "_backend_lock"
                for item in node.items
            )
            if backend:
                self._backend_depth += 1
            self.generic_visit(node)
            if backend:
                self._backend_depth -= 1

        def visit_Call(self, node: ast.Call) -> None:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            if name == "load" and self._backend_depth:
                self.load_under_backend = True
            self.generic_visit(node)

    walk = Walk()
    walk.visit(_warm_dream_fn())
    assert walk.load_under_backend is False
    src = ast.unparse(_warm_dream_fn())
    assert "_infer_lock" in src
    assert "load()" in src
