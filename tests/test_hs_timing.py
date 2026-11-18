from __future__ import annotations

import ast
from pathlib import Path

SRC = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "specs"
    / "Voice_Bot"
    / "pod-artifacts"
    / "hs_timing.py"
)


def test_importing_hs_timing_does_not_connect() -> None:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))

    def _runs_main(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if child.func.attr == "run":
                    return True
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "main":
                return True
        return False

    module_level = [node for node in tree.body if _runs_main(node)]
    assert module_level, "main must still run from this file"
    for node in module_level:
        assert isinstance(node, ast.If), "importing hs_timing.py must not connect"
        test = node.test
        assert isinstance(test, ast.Compare)
        assert isinstance(test.left, ast.Name) and test.left.id == "__name__"
