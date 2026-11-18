from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import torch

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "moshi"
    / "moshi"
    / "moshi"
    / "server.py"
)


def _warmup():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ServerState":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "warmup":
                    module = ast.Module(body=[item], type_ignores=[])
                    ast.fix_missing_locations(module)
                    namespace: dict[str, object] = {"torch": torch}
                    exec(compile(module, str(SRC), "exec"), namespace)
                    return namespace["warmup"]
    raise AssertionError("ServerState.warmup not found")


def _state(device: str):
    codes = torch.zeros(1, 1, 1)

    def encode(_chunk):
        return codes

    def step(_codes):
        return None

    return SimpleNamespace(
        device=device,
        frame_size=4,
        mimi=SimpleNamespace(encode=encode, decode=lambda tokens: tokens),
        lm_gen=SimpleNamespace(step=step),
    )


def test_cpu_warmup_does_not_call_cuda_synchronize(monkeypatch) -> None:
    called: list[object] = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *a, **k: called.append((a, k)))
    _warmup()(_state("cpu"))
    assert called == []


def test_importing_the_module_does_not_start_main() -> None:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    def _calls_main(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "main":
                return True
        return False

    module_level = [node for node in tree.body if _calls_main(node)]
    assert module_level, "main() must still run from this file"
    for node in module_level:
        assert isinstance(node, ast.If), "importing moshi.server must not call main()"
        test = node.test
        assert isinstance(test, ast.Compare)
        assert isinstance(test.left, ast.Name) and test.left.id == "__name__"


def test_cuda_warmup_synchronizes_the_model_device(monkeypatch) -> None:
    called: list[object] = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda device=None: called.append(device))
    _warmup()(_state("cuda:1"))
    assert called == ["cuda:1"]
