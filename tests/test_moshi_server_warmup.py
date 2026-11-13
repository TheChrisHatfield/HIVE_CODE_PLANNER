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


def test_cuda_warmup_synchronizes_the_model_device(monkeypatch) -> None:
    called: list[object] = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda device=None: called.append(device))
    _warmup()(_state("cuda:1"))
    assert called == ["cuda:1"]
